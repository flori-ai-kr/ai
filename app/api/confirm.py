"""확인 카드 실행 — 사용자가 제안을 확인하면 백엔드 쓰기를 실행한다(human-in-loop의 종착점)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_backend_client, get_pending_store, get_request_context
from app.backend.auth import RequestContext
from app.backend.client import BackendClient, BackendError
from app.confirm.executor import execute
from app.confirm.store import PendingNotFound, PendingWriteStore
from app.core.audit import audit_event

router = APIRouter()


class ConfirmRequest(BaseModel):
    proposal_id: str = Field(..., max_length=64)


class ConfirmResponse(BaseModel):
    action: str
    result: dict[str, Any]


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    req: ConfirmRequest,
    ctx: RequestContext = Depends(get_request_context),
    store: PendingWriteStore = Depends(get_pending_store),
    backend: BackendClient = Depends(get_backend_client),
) -> ConfirmResponse:
    try:
        pending = await store.take(req.proposal_id, user_id=ctx.user_id)
    except PendingNotFound:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없거나 만료되었어요.") from None
    except PermissionError:
        audit_event("confirm_access_denied", user_id=ctx.user_id, proposal_id=req.proposal_id)
        raise HTTPException(status_code=403, detail="proposal access denied") from None

    try:
        result = await execute(backend, ctx, pending)
    except BackendError:
        audit_event("write_failed", user_id=ctx.user_id, action=pending.action)
        raise HTTPException(status_code=502, detail="예약 생성 중 백엔드 오류가 발생했어요.") from None
    except ValueError:
        # 알 수 없는 action(서버 내부 stored 값) — 500 대신 400으로.
        raise HTTPException(status_code=400, detail="처리할 수 없는 요청입니다.") from None

    # payload는 audit_event가 PII를 자동 마스킹(deep)하므로 안전하게 기록.
    audit_event("write_executed", user_id=ctx.user_id, action=pending.action, payload=pending.payload)
    return ConfirmResponse(action=pending.action, result=result)
