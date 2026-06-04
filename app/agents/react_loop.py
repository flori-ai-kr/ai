"""ReAct 도구콜 루프.

LLM에 도구를 bind → tool_calls 디스패치 → ToolMessage 누적 → 최종 응답. iteration cap으로
무한 루프를 막고, 인자 오류는 dispatch가 에러 dict로 돌려 self-correction을 유도한다.
모든 도구 호출은 감사 로깅한다. 모델은 LangChain ``BaseChatModel`` 인터페이스(bind_tools/ainvoke)면
무엇이든 주입 가능(테스트는 fake model).
"""

import asyncio
import json
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.prompts import build_system_prompt, fence_user_input
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.core.audit import audit_event
from app.observability.tracing import observe
from app.session.models import Turn
from app.tools.registry import dispatch, tool_schemas

_CAP_FALLBACK = "지금은 분석을 끝맺지 못했어요. 잠시 후 다시 시도해 주세요."
_MAX_TOOL_RESULT_CHARS = 8_000  # ToolMessage 1건 상한 — 컨텍스트 폭주/메모리 DoS 방지


def _truncate_result(raw: str) -> str:
    if len(raw) > _MAX_TOOL_RESULT_CHARS:
        return raw[:_MAX_TOOL_RESULT_CHARS] + "\n...[truncated]"
    return raw


async def _run_tool_call(client: BackendClient, ctx: RequestContext, call: dict) -> ToolMessage:
    """도구 1건을 감사 로깅 + 디스패치하고 ToolMessage로 직렬화한다(병렬 실행 단위)."""
    name = call["name"]
    args = call.get("args") or {}
    # id가 없으면 고유값 생성 — 동일 도구 연속 호출이 tool_call_id를 공유하는 버그 방지
    call_id = call.get("id") or f"{name}-{uuid.uuid4().hex[:8]}"
    audit_event("tool_call", user_id=ctx.user_id, tool=name, args=args)
    result = await dispatch(client, ctx, name, args)
    content = _truncate_result(json.dumps(result, ensure_ascii=False, default=str))
    return ToolMessage(content=content, tool_call_id=call_id)


def _audit_llm_usage(ctx: RequestContext, ai: AIMessage) -> None:
    """LLM 응답의 토큰 사용량을 감사 로깅한다(비용 가시성). 토큰 수는 PII가 아니다."""
    usage = getattr(ai, "usage_metadata", None)
    if not usage:
        return
    audit_event(
        "llm_usage",
        user_id=ctx.user_id,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


def _history_to_messages(history: list[Turn] | None) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for turn in history or []:
        if turn.role == "user":
            messages.append(HumanMessage(content=turn.text))
        elif turn.role == "assistant":
            messages.append(AIMessage(content=turn.text))
    return messages


@observe(name="run_agent")
async def run_agent(
    *,
    model: BaseChatModel,
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
        _audit_llm_usage(ctx, ai)
        messages.append(ai)

        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            return ai.content or ""

        # 한 턴의 도구 호출은 서로 독립적인 백엔드 읽기(A) — 병렬 실행해 지연을 줄인다.
        # gather가 입력 순서를 보존하므로 ToolMessage는 tool_calls 순서대로 누적된다.
        tool_messages = await asyncio.gather(*(_run_tool_call(client, ctx, call) for call in tool_calls))
        messages.extend(tool_messages)

    # iteration cap 도달 — 무한 루프 방지
    audit_event("agent_cap_reached", user_id=ctx.user_id, iterations=max_iterations)
    return _CAP_FALLBACK
