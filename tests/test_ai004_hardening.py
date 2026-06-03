"""SPEC-AI-004 리뷰 반영(음성 경로 보안/리소스/견고성) 회귀 테스트."""

import base64

import httpx
from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

import app.api.voice as voice_mod
from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_session_store,
    get_stt,
    get_tts,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.main import create_app
from app.session.store import SessionStore
from app.voice.ports import VoiceProviderError


class _Stt:
    def __init__(self, text: str = "내일 2시 예약") -> None:
        self._text = text

    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        return self._text


class _Tts:
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        return (b"AUDIO", "audio/mpeg")


class _BoomTts:
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        raise VoiceProviderError("polly down")


class _Model:
    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="네, 도와드릴게요.")


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _app(*, stt=None, tts=None, store=None):
    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    app.dependency_overrides[get_chat_model] = lambda: _Model()
    app.dependency_overrides[get_backend_client] = lambda: BackendClient("http://backend.test", timeout=5.0)
    app.dependency_overrides[get_session_store] = lambda: store or SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    app.dependency_overrides[get_stt] = lambda: stt or _Stt()
    app.dependency_overrides[get_tts] = lambda: tts or _Tts()
    return app


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


_AUTH = {"Authorization": "Bearer jwt"}


async def test_voice_rejects_oversized_decoded_audio(monkeypatch):
    monkeypatch.setattr(voice_mod, "_MAX_AUDIO_BYTES", 8)
    async with _client(_app()) as c:
        r = await c.post(
            "/voice/turn", json={"audio_base64": _b64(b"0123456789"), "content_type": "audio/wav"}, headers=_AUTH
        )
    assert r.status_code == 413


async def test_voice_rejects_empty_transcript():
    async with _client(_app(stt=_Stt(text="   "))) as c:
        r = await c.post("/voice/turn", json={"audio_base64": _b64(b"aud"), "content_type": "audio/wav"}, headers=_AUTH)
    assert r.status_code == 422


async def test_voice_rejects_unsupported_content_type():
    async with _client(_app()) as c:
        r = await c.post(
            "/voice/turn", json={"audio_base64": _b64(b"aud"), "content_type": "application/json"}, headers=_AUTH
        )
    assert r.status_code == 422


async def test_voice_rejects_malformed_session_id():
    async with _client(_app()) as c:
        r = await c.post(
            "/voice/turn",
            json={"audio_base64": _b64(b"aud"), "content_type": "audio/wav", "session_id": "flori:session:victim"},
            headers=_AUTH,
        )
    assert r.status_code == 422


async def test_voice_wrong_owner_session_returns_403():
    store = SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    await store.get_or_create("sessx", "owner")
    async with _client(_app(store=store)) as c:
        r = await c.post(
            "/voice/turn",
            json={"audio_base64": _b64(b"aud"), "content_type": "audio/wav", "session_id": "sessx"},
            headers=_AUTH,
        )
    assert r.status_code == 403


async def test_voice_tts_provider_error_returns_502():
    async with _client(_app(tts=_BoomTts())) as c:
        r = await c.post("/voice/turn", json={"audio_base64": _b64(b"aud"), "content_type": "audio/wav"}, headers=_AUTH)
    assert r.status_code == 502
