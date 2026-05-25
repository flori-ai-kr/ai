"""선제 제안 엔드포인트 (D). 읽기전용 — 제안은 표시일 뿐, 실행은 confirm 경유."""

from typing import Any

from fastapi import APIRouter, Depends
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.agents.proactive import Suggestion, generate_proactive_suggestions
from app.api.deps import get_backend_client, get_chat_model, get_request_context
from app.backend.auth import RequestContext
from app.backend.client import BackendClient

router = APIRouter()


class ProactiveResponse(BaseModel):
    suggestions: list[Suggestion]


@router.get("/agent/proactive", response_model=ProactiveResponse)
async def proactive(
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_chat_model),
    backend: BackendClient = Depends(get_backend_client),
) -> ProactiveResponse:
    suggestions: list[Any] = await generate_proactive_suggestions(model=model, client=backend, ctx=ctx)
    return ProactiveResponse(suggestions=suggestions)
