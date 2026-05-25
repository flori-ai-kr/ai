"""채팅 엔드포인트 (A 데이터 분석).

인증 → 세션 get_or_create + 유저 턴 기록 → ReAct 에이전트 실행 → 어시스턴트 턴 기록 → 응답.
session_id는 클라이언트가 주거나, 없으면 서버가 발급한다(소유자 검증은 세션 스토어가 강제).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.react_loop import run_agent
from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_session_store,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.session.models import Turn
from app.session.store import SessionStore

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: Any = Depends(get_chat_model),
    backend: BackendClient = Depends(get_backend_client),
    store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    session_id = req.session_id or uuid.uuid4().hex
    session = await store.get_or_create(session_id, ctx.user_id)

    history = list(session.turns)  # 이번 메시지 이전까지의 맥락
    await store.append_turn(session_id, Turn(role="user", text=req.message), user_id=ctx.user_id)

    reply = await run_agent(model=model, client=backend, ctx=ctx, user_text=req.message, history=history)

    await store.append_turn(session_id, Turn(role="assistant", text=reply), user_id=ctx.user_id)
    return ChatResponse(reply=reply, session_id=session_id)
