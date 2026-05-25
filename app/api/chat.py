"""채팅 엔드포인트 (A 데이터 분석).

인증 → 세션 get_or_create + 유저 턴 기록 → ReAct 에이전트 실행 → 어시스턴트 턴 기록 → 응답.
session_id는 클라이언트가 주거나, 없으면 서버가 발급한다(소유자 검증은 세션 스토어가 강제).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.react_loop import run_agent
from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_session_store,
)
from app.api.validators import SafeId
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.core.audit import audit_event
from app.session.models import Turn
from app.session.store import SessionStore

router = APIRouter()

_AGENT_ERROR_REPLY = "죄송해요, 분석 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요."


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: SafeId | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_chat_model),
    backend: BackendClient = Depends(get_backend_client),
    store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    session_id = req.session_id or uuid.uuid4().hex
    try:
        session = await store.get_or_create(session_id, ctx.user_id)
    except PermissionError:
        audit_event("session_access_denied", user_id=ctx.user_id, session_id=session_id)
        raise HTTPException(status_code=403, detail="session access denied") from None

    history = list(session.turns)  # 이번 메시지 이전까지의 맥락
    await store.append_turn(session_id, Turn(role="user", text=req.message), user_id=ctx.user_id)

    try:
        reply = await run_agent(model=model, client=backend, ctx=ctx, user_text=req.message, history=history)
    except Exception:
        # 에이전트/LLM 실패 시에도 세션이 절반만 기록되지 않게 폴백 응답을 기록하고 반환.
        audit_event("chat_agent_error", user_id=ctx.user_id, session_id=session_id)
        reply = _AGENT_ERROR_REPLY

    await store.append_turn(session_id, Turn(role="assistant", text=reply), user_id=ctx.user_id)
    return ChatResponse(reply=reply, session_id=session_id)
