"""채팅 엔드포인트 (A 데이터 분석) — 게이트웨이 뒤 stateless.

게이트웨이가 전체 대화 히스토리(messages)를 보낸다. ai-server는 세션을 소유하지 않는다.
인증 → ReAct 에이전트 실행 → 응답(reply + 사용 모델). 영속/세션/캡은 게이트웨이가 소유.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.react_loop import run_agent
from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_settings,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.core.audit import audit_event
from app.core.config import Settings
from app.session.models import Turn

router = APIRouter()

_AGENT_ERROR_REPLY = "죄송해요, 분석 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요."


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    # 게이트웨이가 보내는 전체 대화 히스토리(마지막 항목 = 이번 유저 발화). 길이 상한으로 컨텍스트 폭발 방어.
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=50)
    model: str | None = None  # 게이트웨이 힌트(현재는 ai-server 설정 모델을 사용)


class ChatResponse(BaseModel):
    reply: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_chat_model),
    backend: BackendClient = Depends(get_backend_client),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    *prior, last = req.messages
    if last.role != "user":
        raise HTTPException(status_code=422, detail="last message must be from user")
    history = [Turn(role=m.role, text=m.content) for m in prior]

    try:
        reply = await run_agent(model=model, client=backend, ctx=ctx, user_text=last.content, history=history)
    except Exception:
        audit_event("chat_agent_error", user_id=ctx.user_id)
        reply = _AGENT_ERROR_REPLY

    return ChatResponse(reply=reply, model=settings.llm_model)
