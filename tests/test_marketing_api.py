import httpx

from app.agents.marketing.schemas import BlogDraft, BlogFaq, BlogSection
from app.api.deps import get_marketing_chat_model, get_request_context
from app.backend.auth import RequestContext
from app.main import create_app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _valid_draft() -> BlogDraft:
    return BlogDraft(
        title="어버이날 카네이션 꽃다발 추천",
        sections=[BlogSection(heading=f"질문{i}", body="자기완결 단락 본문입니다.") for i in range(3)],
        faq=[BlogFaq(q="가격은?", a="범위로 안내드려요.") for _ in range(3)],
        hashtags=["#어버이날", "#카네이션", "#꽃집"],
    )


class _StructuredModel:
    def __init__(self, draft: BlogDraft) -> None:
        self._draft = draft

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        return self._draft


def _app_with_model(model):
    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    app.dependency_overrides[get_marketing_chat_model] = lambda: model
    return app


async def test_blog_endpoint_keyword_only_returns_draft():
    app = _app_with_model(_StructuredModel(_valid_draft()))
    async with _client(app) as c:
        r = await c.post("/marketing/blog", json={"keyword": "어버이날 카네이션 꽃다발"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draft"]["title"]
    assert len(body["draft"]["sections"]) >= 3
    assert len(body["draft"]["faq"]) >= 3
    assert len(body["draft"]["hashtags"]) >= 3
    assert body["model"]


async def test_blog_endpoint_requires_internal_key():
    # 게이트웨이 신뢰 인증: override 없으면 401
    async with _client(create_app()) as c:
        r = await c.post("/marketing/blog", json={"keyword": "x"})
    assert r.status_code == 401


async def test_blog_endpoint_rejects_private_photo_url():
    app = _app_with_model(_StructuredModel(_valid_draft()))
    async with _client(app) as c:
        for bad in ["http://169.254.169.254/x.png", "http://127.0.0.1/a.png", "file:///etc/passwd"]:
            r = await c.post("/marketing/blog", json={"keyword": "장미", "photo_urls": [bad]})
            assert r.status_code == 422, bad


async def test_blog_endpoint_rejects_empty_keyword():
    app = _app_with_model(_StructuredModel(_valid_draft()))
    async with _client(app) as c:
        r = await c.post("/marketing/blog", json={"keyword": ""})
    assert r.status_code == 422


async def test_blog_endpoint_accepts_text_prompt_override():
    # 텍스트 override(system_md)만 → 모델 재빌드 없이 주입 모델 사용, 프롬프트에 반영
    captured = {}

    class _Capturing(_StructuredModel):
        async def ainvoke(self, messages):
            captured["messages"] = str(messages)
            return self._draft

    app = _app_with_model(_Capturing(_valid_draft()))
    async with _client(app) as c:
        r = await c.post(
            "/marketing/blog",
            json={"keyword": "장미", "prompt_override": {"system_md": "<<CUSTOM SYS>>"}},
        )
    assert r.status_code == 200, r.text
    assert "<<CUSTOM SYS>>" in captured["messages"]


async def test_blog_endpoint_override_model_and_temp_rebuilds_model(monkeypatch):
    # model/temperature override → build_chat_model로 요청 단위 재빌드(인수기준 3)
    captured = {}
    mock = _StructuredModel(_valid_draft())

    def _fake_build(settings, *, model=None, temperature=0.0):
        captured["model"] = model
        captured["temperature"] = temperature
        return mock

    monkeypatch.setattr("app.api.marketing.build_chat_model", _fake_build)
    app = _app_with_model(_StructuredModel(_valid_draft()))
    async with _client(app) as c:
        r = await c.post(
            "/marketing/blog",
            json={
                "keyword": "장미",
                "prompt_override": {"model": "claude-sonnet-4-6", "temperature": 0.3},
            },
        )
    assert r.status_code == 200, r.text
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["temperature"] == 0.3
    assert r.json()["model"] == "claude-sonnet-4-6"


async def test_blog_endpoint_logs_generation_steps(caplog):
    # 스텝 로그(📥 요청 수신 → ✅ 생성 완료)가 flori.marketing 로거로 남는지 가드
    app = _app_with_model(_StructuredModel(_valid_draft()))
    with caplog.at_level("INFO", logger="flori.marketing"):
        async with _client(app) as c:
            r = await c.post("/marketing/blog", json={"keyword": "장미"})
    assert r.status_code == 200, r.text
    blob = "\n".join(caplog.messages)
    assert "블로그 생성 요청 수신" in blob  # 📥
    assert "프롬프트 조립 완료" in blob  # 🧱
    assert "블로그 초안 생성 완료" in blob  # ✅


async def test_blog_endpoint_passes_store_context_and_tone():
    captured = {}

    class _Capturing(_StructuredModel):
        async def ainvoke(self, messages):
            captured["messages"] = str(messages)
            return self._draft

    app = _app_with_model(_Capturing(_valid_draft()))
    async with _client(app) as c:
        r = await c.post(
            "/marketing/blog",
            json={
                "keyword": "장미 꽃다발",
                "tone_samples": ["내 블로그 말투"],
                "store_context": {"shop_name": "플로리", "avg_order_value": 55000},
            },
        )
    assert r.status_code == 200, r.text
    assert "플로리" in captured["messages"]
    assert "내 블로그 말투" in captured["messages"]
