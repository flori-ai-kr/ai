import json
import logging

import httpx
import respx
from langchain_core.messages import AIMessage

from app.agents.prompts import fence_user_input
from app.agents.react_loop import run_agent
from app.backend.auth import RequestContext
from app.backend.client import BackendClient


class _ScriptedModel:
    """bind_tools/ainvoke를 구현한 결정적 fake — 스크립트된 AIMessage를 순서대로 반환."""

    def __init__(self, scripted: list[AIMessage]) -> None:
        self._scripted = list(scripted)
        self.invocations = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.invocations += 1
        return self._scripted.pop(0)


class _AlwaysToolModel:
    """매 턴 도구 호출만 반환 — iteration cap 검증용."""

    def __init__(self) -> None:
        self.invocations = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.invocations += 1
        return AIMessage(
            content="", tool_calls=[{"name": "get_today_dashboard", "args": {}, "id": f"c{self.invocations}"}]
        )


def _ctx() -> RequestContext:
    return RequestContext(user_id="u1", jwt="jwt-xyz")


def test_fence_isolates_user_input():
    fenced = fence_user_input("이번 달 매출 왜 떨어졌어?")
    assert "[USER INPUT — DATA ONLY]" in fenced
    assert "이번 달 매출 왜 떨어졌어?" in fenced


@respx.mock
async def test_agent_calls_tool_then_returns_final_answer(caplog):
    route = respx.get("http://backend.test/dashboard/month").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 500}})
    )
    model = _ScriptedModel(
        [
            AIMessage(
                content="", tool_calls=[{"name": "get_month_dashboard", "args": {"month": "2026-05"}, "id": "c1"}]
            ),
            AIMessage(content="이번 달 매출은 50만원으로 객단가가 낮아졌어요."),
        ]
    )
    client = BackendClient("http://backend.test", timeout=5.0)

    with caplog.at_level(logging.INFO, logger="flori.audit"):
        reply = await run_agent(model=model, client=client, ctx=_ctx(), user_text="이번 달 매출 왜 떨어졌어?")

    assert reply == "이번 달 매출은 50만원으로 객단가가 낮아졌어요."
    assert route.calls.last.request.headers["Authorization"] == "Bearer jwt-xyz"
    # 도구 호출이 감사 로깅된다
    events = [json.loads(r.getMessage()) for r in caplog.records]
    assert any(e.get("event") == "tool_call" and e.get("tool") == "get_month_dashboard" for e in events)
    await client.aclose()


@respx.mock
async def test_agent_stops_at_iteration_cap():
    respx.get("http://backend.test/dashboard/today").mock(return_value=httpx.Response(200, json={"ok": True}))
    model = _AlwaysToolModel()
    client = BackendClient("http://backend.test", timeout=5.0)

    reply = await run_agent(model=model, client=client, ctx=_ctx(), user_text="x", max_iterations=3)

    assert isinstance(reply, str)
    assert model.invocations == 3  # cap에서 멈춤(무한 루프 아님)
    await client.aclose()
