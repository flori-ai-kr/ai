"""FastAPI 의존성. app.state의 자원을 주입하고, 인증·사용량 캡을 강제한다."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request

from app.backend.auth import Authenticator, AuthError, RequestContext
from app.core.usage import UsageCapExceeded, UsageLimiter
from app.session.store import SessionStore

_BEARER_PREFIX = "Bearer "
_KST = ZoneInfo("Asia/Seoul")


def _seconds_until_kst_midnight() -> int:
    """일일 캡 리셋(KST 자정)까지 남은 초 — 429 Retry-After용."""
    now = datetime.now(_KST)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def get_authenticator(request: Request) -> Authenticator:
    return request.app.state.authenticator


def get_usage_limiter(request: Request) -> UsageLimiter:
    return request.app.state.usage_limiter


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_backend_client(request: Request):
    return request.app.state.backend


def get_chat_model(request: Request):
    return request.app.state.chat_model


async def get_request_context(
    request: Request,
    authenticator: Authenticator = Depends(get_authenticator),
    usage: UsageLimiter = Depends(get_usage_limiter),
) -> RequestContext:
    """``Authorization: Bearer`` 추출 → /me 검증 → 사용량 캡. 실패 시 401/429."""
    authz = request.headers.get("Authorization", "")
    if not authz.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="missing bearer token")
    jwt = authz[len(_BEARER_PREFIX) :].strip()
    if not jwt:
        raise HTTPException(status_code=401, detail="empty bearer token")

    try:
        ctx = await authenticator.authenticate(jwt)
    except AuthError:
        raise HTTPException(status_code=401, detail="invalid or expired token") from None

    try:
        await usage.enforce(ctx.user_id)
    except UsageCapExceeded:
        raise HTTPException(
            status_code=429,
            detail="daily usage cap exceeded",
            headers={"Retry-After": str(_seconds_until_kst_midnight())},
        ) from None

    return ctx
