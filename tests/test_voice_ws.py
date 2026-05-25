import base64
import json

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import WebSocketDisconnect
from langchain_core.messages import AIMessage
from starlette.testclient import TestClient

from app.backend.auth import AuthError, RequestContext
from app.backend.client import BackendClient
from app.main import create_app
from app.session.store import SessionStore


class _FakeAuth:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def authenticate(self, jwt: str) -> RequestContext:
        if self._fail or not jwt:
            raise AuthError("bad")
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


class _Stt:
    def __init__(self, text: str = "내일 2시 예약") -> None:
        self._text = text

    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        return self._text


class _Tts:
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        return (b"AUDIO:" + text.encode("utf-8"), "audio/mpeg")


class _Model:
    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="네, 도와드릴게요.")


def _app(*, auth=None, stt=None):
    app = create_app()
    # lifespan을 띄우지 않고(아래 TestClient를 `with` 없이 사용) app.state를 직접 주입
    app.state.authenticator = auth or _FakeAuth()
    app.state.usage_limiter = _FakeUsage()
    app.state.stt = stt or _Stt()
    app.state.tts = _Tts()
    app.state.chat_model = _Model()
    app.state.backend = BackendClient("http://backend.test", timeout=5.0)
    app.state.session_store = SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    return app


def test_ws_voice_turn_streams_events():
    client = TestClient(_app())
    with client.websocket_connect("/voice/stream?token=jwt") as ws:
        ws.send_bytes(b"\x00\x01audio")
        ws.send_text(json.dumps({"type": "end"}))
        t = ws.receive_json()
        assert t["type"] == "transcript" and t["text"] == "내일 2시 예약"
        r = ws.receive_json()
        assert r["type"] == "reply" and r["text"] == "네, 도와드릴게요."
        a = ws.receive_json()
        assert a["type"] == "audio"
        assert base64.b64decode(a["audio_base64"]).startswith(b"AUDIO:")
        d = ws.receive_json()
        assert d["type"] == "done"
        ws.send_text(json.dumps({"type": "close"}))


def test_ws_rejects_bad_token():
    client = TestClient(_app(auth=_FakeAuth(fail=True)))
    with client.websocket_connect("/voice/stream?token=bad") as ws, pytest.raises(WebSocketDisconnect):
        ws.receive_json()


def test_ws_empty_transcript_sends_error_event():
    client = TestClient(_app(stt=_Stt(text="   ")))
    with client.websocket_connect("/voice/stream?token=jwt") as ws:
        ws.send_bytes(b"aud")
        ws.send_text(json.dumps({"type": "end"}))
        e = ws.receive_json()
        assert e["type"] == "error"
        ws.send_text(json.dumps({"type": "close"}))


def test_ws_rejects_malformed_session_id():
    client = TestClient(_app())
    with (
        client.websocket_connect("/voice/stream?token=jwt&session_id=flori:session:victim") as ws,
        pytest.raises(WebSocketDisconnect),
    ):
        ws.receive_json()


def test_ws_rejects_unsupported_content_type():
    client = TestClient(_app())
    with client.websocket_connect("/voice/stream?token=jwt") as ws:
        ws.send_text(json.dumps({"type": "start", "content_type": "application/json"}))
        e = ws.receive_json()
        assert e["type"] == "error"
        ws.send_text(json.dumps({"type": "close"}))


def test_ws_rejects_oversized_audio(monkeypatch):
    import app.api.voice_ws as ws_mod

    monkeypatch.setattr(ws_mod, "_MAX_AUDIO_BYTES", 4)
    client = TestClient(_app())
    with client.websocket_connect("/voice/stream?token=jwt") as ws:
        ws.send_bytes(b"0123456789")
        m = ws.receive_json()
        assert m["type"] == "error"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_multiturn_keeps_session():
    client = TestClient(_app())
    with client.websocket_connect("/voice/stream?token=jwt") as ws:
        ws.send_bytes(b"a")
        ws.send_text(json.dumps({"type": "end"}))
        ws.receive_json()  # transcript
        r1 = ws.receive_json()  # reply
        ws.receive_json()  # audio
        ws.receive_json()  # done
        sid1 = r1["session_id"]

        ws.send_bytes(b"b")
        ws.send_text(json.dumps({"type": "end"}))
        ws.receive_json()
        r2 = ws.receive_json()
        ws.receive_json()
        ws.receive_json()
        assert r2["session_id"] == sid1
        ws.send_text(json.dumps({"type": "close"}))
