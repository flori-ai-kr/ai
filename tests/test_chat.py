import httpx
import respx
from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

from app.api.deps import (
    get_authenticator,
    get_backend_client,
    get_chat_model,
    get_session_store,
    get_usage_limiter,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.main import create_app
from app.session.store import SessionStore


class _FakeAuth:
    async def authenticate(self, jwt: str) -> RequestContext:
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


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
async def test_chat_runs_agent_and_persists_turns():
    respx.get("http://backend.test/dashboard/month").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 500}})
    )
    backend = BackendClient("http://backend.test", timeout=5.0)
    store = SessionStore(FakeAsyncRedis(), ttl_seconds=3600)
    model = _ScriptedModel(
        [
            AIMessage(
                content="", tool_calls=[{"name": "get_month_dashboard", "args": {"month": "2026-05"}, "id": "c1"}]
            ),
            AIMessage(content="이번 달 매출은 50만원이에요."),
        ]
    )

    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_backend_client] = lambda: backend
    app.dependency_overrides[get_session_store] = lambda: store

    async with _client(app) as c:
        r = await c.post(
            "/chat", json={"message": "이번 달 매출 왜 떨어졌어?"}, headers={"Authorization": "Bearer jwt"}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "이번 달 매출은 50만원이에요."
    assert body["session_id"]

    session = await store.get(body["session_id"])
    assert session is not None
    assert [t.role for t in session.turns] == ["user", "assistant"]
    assert session.user_id == "u1"
    await backend.aclose()


async def test_chat_requires_auth():
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    async with _client(app) as c:
        r = await c.post("/chat", json={"message": "hi"})
    assert r.status_code == 401
