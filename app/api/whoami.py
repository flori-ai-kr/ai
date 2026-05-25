"""보호 엔드포인트 예시 — 인증 의존성(JWT 패스스루 검증)이 동작함을 보인다.

기능 라우터(chat/confirm/voice)는 후속 SPEC에서 동일한 ``get_request_context``를 쓴다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_request_context
from app.backend.auth import RequestContext

router = APIRouter()


@router.get("/whoami")
async def whoami(ctx: RequestContext = Depends(get_request_context)) -> dict:
    return {"user_id": ctx.user_id}
