import httpx
import respx
from langchain_core.messages import AIMessage

from app.agents.proactive import _SYSTEM, generate_proactive_suggestions
from app.api.deps import get_backend_client, get_chat_model, get_request_context
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.main import create_app

_SUGGESTIONS_JSON = (
    '[{"title":"내일 예약 3건","detail":"리마인더를 보낼까요?"},'
    '{"title":"매출 점검","detail":"이번 주 카드매출 비중이 늘었어요."}]'
)


class _Model:
    def __init__(self, content: str = _SUGGESTIONS_JSON) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return AIMessage(content=self._content)


class _CapturingModel(_Model):
    """ainvoke 에 전달된 messages 를 보존해 프롬프트 구성을 검증한다."""

    def __init__(self, content: str = _SUGGESTIONS_JSON) -> None:
        super().__init__(content)
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return await super().ainvoke(messages)


def _ctx() -> RequestContext:
    return RequestContext(user_id="u1", jwt="jwt-xyz")


def _mock_backend_ok():
    respx.get("http://backend.test/dashboard/today").mock(return_value=httpx.Response(200, json={"summary": {}}))
    respx.get("http://backend.test/reservations/upcoming").mock(return_value=httpx.Response(200, json=[]))


@respx.mock
async def test_proactive_reads_context_with_jwt_and_parses_suggestions():
    route = respx.get("http://backend.test/dashboard/today").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 100}})
    )
    respx.get("http://backend.test/reservations/upcoming").mock(return_value=httpx.Response(200, json=[]))
    client = BackendClient("http://backend.test", timeout=5.0)

    suggestions = await generate_proactive_suggestions(model=_Model(), client=client, ctx=_ctx())

    assert len(suggestions) == 2
    assert suggestions[0].title == "내일 예약 3건"
    assert route.calls.last.request.headers["Authorization"] == "Bearer jwt-xyz"
    await client.aclose()


@respx.mock
async def test_proactive_fail_open_on_backend_error():
    respx.get("http://backend.test/dashboard/today").mock(return_value=httpx.Response(500))
    respx.get("http://backend.test/reservations/upcoming").mock(return_value=httpx.Response(500))
    client = BackendClient("http://backend.test", timeout=5.0, max_retries=0)
    # 백엔드 오류여도 크래시 없이 동작(컨텍스트 degrade)
    suggestions = await generate_proactive_suggestions(model=_Model(), client=client, ctx=_ctx())
    assert isinstance(suggestions, list)
    await client.aclose()


@respx.mock
async def test_proactive_fail_open_on_bad_model_output():
    _mock_backend_ok()
    client = BackendClient("http://backend.test", timeout=5.0)
    suggestions = await generate_proactive_suggestions(model=_Model(content="죄송해요"), client=client, ctx=_ctx())
    assert suggestions == []
    await client.aclose()


@respx.mock
async def test_proactive_fences_backend_context_as_data():
    """회귀: 백엔드 컨텍스트는 [CONTEXT — DATA ONLY] 펜스로 격리되고 시스템 프롬프트가 _SYSTEM 이어야 한다.

    펜스 토큰이 깨지면 컨텍스트 안의 텍스트가 지시로 해석될 위험(인젝션) → 토큰을 고정한다.
    """
    _mock_backend_ok()
    client = BackendClient("http://backend.test", timeout=5.0)
    model = _CapturingModel()

    await generate_proactive_suggestions(model=model, client=client, ctx=_ctx())

    assert model.messages is not None, "ainvoke가 호출되지 않음"
    system_msg, human_msg = model.messages
    assert system_msg.content == _SYSTEM
    assert human_msg.content.startswith("[CONTEXT — DATA ONLY]\n")
    await client.aclose()


# --- 엔드포인트 ---
def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@respx.mock
async def test_proactive_endpoint_returns_suggestions():
    _mock_backend_ok()
    backend = BackendClient("http://backend.test", timeout=5.0)
    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    app.dependency_overrides[get_chat_model] = lambda: _Model()
    app.dependency_overrides[get_backend_client] = lambda: backend

    async with _client(app) as c:
        r = await c.get("/agent/proactive")
    assert r.status_code == 200
    body = r.json()
    assert len(body["suggestions"]) == 2
    assert body["suggestions"][0]["title"] == "내일 예약 3건"
    assert body["model"]  # 사용 모델 기록
    await backend.aclose()


async def test_proactive_endpoint_requires_auth():
    # 게이트웨이 내부키 없으면 401.
    async with _client(create_app()) as c:
        r = await c.get("/agent/proactive")
    assert r.status_code == 401
