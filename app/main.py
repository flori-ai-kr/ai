"""FastAPI 엔트리포인트 + lifespan.

lifespan에서 Redis 풀·백엔드 클라이언트·인증기·사용량 캡·세션 스토어를 app.state에
구성한다(자원 생성은 lazy — 연결은 첫 명령 시). 실제 트래픽 처리는 후속 SPEC.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import from_url

from app.agents.llm_client import build_chat_model, build_marketing_chat_model
from app.api import chat, health, marketing, ocr, proactive, voice, voice_ws, whoami
from app.backend.auth import Authenticator
from app.backend.client import BackendClient
from app.confirm.store import PendingWriteStore
from app.core.config import get_settings
from app.core.usage import UsageLimiter
from app.session.store import SessionStore
from app.voice.aws import PollyTts, TranscribeStt


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    redis = from_url(settings.redis_url, decode_responses=True)
    backend = BackendClient(settings.backend_base_url, timeout=settings.request_timeout_seconds)

    app.state.settings = settings
    app.state.redis = redis
    app.state.backend = backend
    app.state.authenticator = Authenticator(backend, cache_ttl_seconds=settings.me_cache_ttl_seconds)
    app.state.usage_limiter = UsageLimiter(redis, cap=settings.usage_cap_per_day)
    app.state.session_store = SessionStore(redis, ttl_seconds=settings.session_ttl_seconds)
    app.state.pending_store = PendingWriteStore(redis, ttl_seconds=settings.pending_ttl_seconds)
    app.state.chat_model = build_chat_model(settings)
    app.state.marketing_chat_model = build_marketing_chat_model(settings)
    app.state.stt = TranscribeStt(language=settings.transcribe_language, region=settings.aws_region)
    app.state.tts = PollyTts(voice=settings.polly_voice, region=settings.aws_region)

    try:
        yield
    finally:
        await backend.aclose()
        await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Flori AI", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(whoami.router)
    app.include_router(chat.router)
    app.include_router(ocr.router)
    app.include_router(marketing.router)
    app.include_router(voice.router)
    app.include_router(voice_ws.router)
    app.include_router(proactive.router)
    return app


app = create_app()
