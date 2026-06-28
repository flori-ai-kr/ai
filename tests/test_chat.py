import httpx
import respx
from langchain_core.messages import AIMessage

from app.api.deps import get_backend_client, get_chat_model, get_request_context
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.main import create_app


class _ScriptedModel:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self._scripted.pop(0)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@respx.mock
async def test_chat_runs_agent_with_provided_history():
    # 게이트웨이가 전체 히스토리(messages)를 보낸다 — ai-server는 세션을 소유하지 않는다.
    respx.get("http://backend.test/dashboard/month").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 500}})
    )
    backend = BackendClient("http://backend.test", timeout=5.0)
    model = _ScriptedModel(
        [
            AIMessage(
                content="", tool_calls=[{"name": "get_month_dashboard", "args": {"month": "2026-05"}, "id": "c1"}]
            ),
            AIMessage(content="이번 달 매출은 50만원이에요."),
        ]
    )

    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_backend_client] = lambda: backend

    async with _client(app) as c:
        r = await c.post(
            "/chat",
            json={
                "messages": [
                    {"role": "user", "content": "지난 매출은?"},
                    {"role": "assistant", "content": "지난달은 60만원이었어요."},
                    {"role": "user", "content": "이번 달 매출 왜 떨어졌어?"},
                ]
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "이번 달 매출은 50만원이에요."
    assert body["model"]
    await backend.aclose()


async def test_chat_requires_auth():
    # 게이트웨이 내부키 없으면 401.
    async with _client(create_app()) as c:
        r = await c.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401
