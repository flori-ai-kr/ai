import httpx
import respx

from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.tools.registry import REGISTRY, dispatch, tool_schemas


def _ctx() -> RequestContext:
    return RequestContext(user_id="u1", jwt="jwt-xyz")


def test_registry_tools_are_openai_schemas_and_read_only():
    schemas = tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert "get_month_dashboard" in names
    assert "list_sales" in names
    for s in schemas:
        assert s["type"] == "function"
        assert "parameters" in s["function"]
    # A 단계는 전부 읽기전용
    assert all(spec.is_write is False for spec in REGISTRY.values())


@respx.mock
async def test_dispatch_forwards_jwt_and_returns_backend_data():
    route = respx.get("http://backend.test/dashboard/month").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 1000}})
    )
    client = BackendClient("http://backend.test", timeout=5.0)
    result = await dispatch(client, _ctx(), "get_month_dashboard", {"month": "2026-05"})

    assert result == {"summary": {"total": 1000}}
    assert route.calls.last.request.headers["Authorization"] == "Bearer jwt-xyz"
    assert route.calls.last.request.url.params["month"] == "2026-05"
    await client.aclose()


async def test_dispatch_unknown_tool_returns_error_not_raise():
    client = BackendClient("http://backend.test", timeout=5.0)
    result = await dispatch(client, _ctx(), "nonexistent_tool", {})
    assert "error" in result
    await client.aclose()


async def test_dispatch_invalid_args_returns_error_for_self_correction():
    client = BackendClient("http://backend.test", timeout=5.0)
    # month는 문자열(YYYY-MM) — 정수는 거부되어 에러 dict 반환(예외 아님)
    result = await dispatch(client, _ctx(), "get_month_dashboard", {"month": 123})
    assert "error" in result
    await client.aclose()
