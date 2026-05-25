"""ReAct 도구콜 루프.

LLM에 도구를 bind → tool_calls 디스패치 → ToolMessage 누적 → 최종 응답. iteration cap으로
무한 루프를 막고, 인자 오류는 dispatch가 에러 dict로 돌려 self-correction을 유도한다.
모든 도구 호출은 감사 로깅한다. 모델은 LangChain ``BaseChatModel`` 인터페이스(bind_tools/ainvoke)면
무엇이든 주입 가능(테스트는 fake model).
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.prompts import build_system_prompt, fence_user_input
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.core.audit import audit_event
from app.session.models import Turn
from app.tools.registry import dispatch, tool_schemas

_CAP_FALLBACK = "지금은 분석을 끝맺지 못했어요. 잠시 후 다시 시도해 주세요."


def _history_to_messages(history: list[Turn] | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for turn in history or []:
        if turn.role == "user":
            messages.append(HumanMessage(content=turn.text))
        elif turn.role == "assistant":
            messages.append(AIMessage(content=turn.text))
    return messages


async def run_agent(
    *,
    model: Any,
    client: BackendClient,
    ctx: RequestContext,
    user_text: str,
    history: list[Turn] | None = None,
    max_iterations: int = 5,
) -> str:
    """도구콜 루프를 돌려 최종 응답 텍스트를 반환한다."""
    messages: list[BaseMessage] = [SystemMessage(content=build_system_prompt())]
    messages.extend(_history_to_messages(history))
    messages.append(HumanMessage(content=fence_user_input(user_text)))

    bound = model.bind_tools(tool_schemas())

    for _ in range(max_iterations):
        ai: AIMessage = await bound.ainvoke(messages)
        messages.append(ai)

        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            return ai.content or ""

        for call in tool_calls:
            name = call["name"]
            args = call.get("args") or {}
            call_id = call.get("id") or name
            audit_event("tool_call", user_id=ctx.user_id, tool=name, args=args)
            result = await dispatch(client, ctx, name, args)
            messages.append(
                ToolMessage(content=json.dumps(result, ensure_ascii=False, default=str), tool_call_id=call_id)
            )

    # iteration cap 도달 — 무한 루프 방지
    return _CAP_FALLBACK
