import base64

import httpx
from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

from app.api.deps import (
    get_authenticator,
    get_backend_client,
    get_chat_model,
    get_session_store,
    get_stt,
    get_tts,
    get_usage_limiter,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.main import create_app
from app.session.store import SessionStore


class _FakeAuth:
    async def authenticate(self, jwt: str) -> RequestContext:
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


class _FakeStt:
    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        return "내일 2시 예약 잡아줘"


class _FakeTts:
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        return (b"AUDIO:" + text.encode("utf-8"), "audio/mpeg")


class _ScriptedModel:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self._scripted.pop(0)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _voice_app():
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_chat_model] = lambda: _ScriptedModel([AIMessage(content="네, 예약 도와드릴게요.")])
    app.dependency_overrides[get_backend_client] = lambda: BackendClient("http://backend.test", timeout=5.0)
    app.dependency_overrides[get_session_store] = lambda: SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    app.dependency_overrides[get_stt] = lambda: _FakeStt()
    app.dependency_overrides[get_tts] = lambda: _FakeTts()
    return app


async def test_voice_turn_returns_transcript_reply_and_audio():
    audio_b64 = base64.b64encode(b"\x00\x01raw").decode()
    async with _client(_voice_app()) as c:
        r = await c.post(
            "/voice/turn",
            json={"audio_base64": audio_b64, "content_type": "audio/wav"},
            headers={"Authorization": "Bearer jwt"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "내일 2시 예약 잡아줘"
    assert body["reply"] == "네, 예약 도와드릴게요."
    assert body["content_type"] == "audio/mpeg"
    assert body["session_id"]
    # audio_base64는 디코딩 가능하고 TTS 출력을 담고 있다
    assert base64.b64decode(body["audio_base64"]).startswith(b"AUDIO:")


async def test_voice_turn_requires_auth():
    audio_b64 = base64.b64encode(b"x").decode()
    async with _client(_voice_app()) as c:
        r = await c.post("/voice/turn", json={"audio_base64": audio_b64, "content_type": "audio/wav"})
    assert r.status_code == 401


async def test_voice_turn_rejects_bad_base64():
    async with _client(_voice_app()) as c:
        r = await c.post(
            "/voice/turn",
            json={"audio_base64": "!!!not-base64!!!", "content_type": "audio/wav"},
            headers={"Authorization": "Bearer jwt"},
        )
    assert r.status_code == 422
