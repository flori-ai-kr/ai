"""FastAPI 의존성. app.state의 자원을 주입하고, 게이트웨이 신뢰 인증을 강제한다.

이 서비스는 Spring 게이트웨이 뒤의 내부망 전용이다 — JWT를 직접 검증(/me)하지 않고
게이트웨이가 보낸 ``X-Internal-Key``를 신뢰한다. ``X-User-Id``로 테넌트를 식별하고,
``Authorization: Bearer``의 유저 JWT는 백엔드(Spring) 도구 호출에 그대로 패스스루한다.
세션/대화 히스토리/사용량 캡은 게이트웨이가 소유한다(여기선 강제하지 않음).
"""

import hmac

from fastapi import Depends, HTTPException, Request
from langchain_core.language_models import BaseChatModel

from app.backend.auth import Authenticator, RequestContext
from app.backend.client import BackendClient
from app.confirm.store import PendingWriteStore
from app.core.config import Settings
from app.core.config import get_settings as _load_settings
from app.core.usage import UsageLimiter
from app.session.store import SessionStore
from app.voice.ports import SttProvider, TtsProvider

_BEARER_PREFIX = "Bearer "


def get_settings() -> Settings:
    """프로세스 단위 싱글톤 설정(lifespan 비의존 — 테스트/운영 공통)."""
    return _load_settings()


def get_authenticator(request: Request) -> Authenticator:
    return request.app.state.authenticator


def get_usage_limiter(request: Request) -> UsageLimiter:
    return request.app.state.usage_limiter


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_backend_client(request: Request) -> BackendClient:
    return request.app.state.backend


def get_chat_model(request: Request) -> BaseChatModel:
    return request.app.state.chat_model


def get_pending_store(request: Request) -> PendingWriteStore:
    return request.app.state.pending_store


def get_stt(request: Request) -> SttProvider:
    return request.app.state.stt


def get_tts(request: Request) -> TtsProvider:
    return request.app.state.tts


async def get_request_context(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RequestContext:
    """게이트웨이 신뢰 인증: ``X-Internal-Key`` 검증 + ``X-User-Id`` + 유저 JWT 패스스루. 실패 시 401."""
    expected = settings.internal_key
    provided = request.headers.get("X-Internal-Key", "")
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid internal key")

    user_id = request.headers.get("X-User-Id", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="missing user id")

    # 유저 JWT는 백엔드(Spring) 도구 호출에 패스스루된다. 게이트웨이가 항상 함께 보낸다.
    authz = request.headers.get("Authorization", "")
    jwt = authz[len(_BEARER_PREFIX) :].strip() if authz.startswith(_BEARER_PREFIX) else ""

    return RequestContext(user_id=user_id, jwt=jwt)
