import httpx
import respx
from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

from app.api.deps import (
    get_authenticator,
    get_backend_client,
    get_chat_model,
    get_pending_store,
    get_usage_limiter,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.confirm.store import PendingWriteStore
from app.main import create_app
from app.session.models import PendingWrite


class _FakeAuth:
    async def authenticate(self, jwt: str) -> RequestContext:
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


class _VisionModel:
    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return AIMessage(content=self._content)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _ocr_app(model, store):
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_pending_store] = lambda: store
    return app


async def test_ocr_returns_card_and_stores_pending():
    store = PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)
    model = _VisionModel(
        '{"customer_name":"김미영","customer_phone":"010-1234-5678",'
        '"date":"2026-05-26","time":"14:00","title":"장미 다발","amount":30000}'
    )
    app = _ocr_app(model, store)
    async with _client(app) as c:
        r = await c.post(
            "/ocr/reservation",
            json={"image_url": "https://img.example/kakao.png"},
            headers={"Authorization": "Bearer jwt"},
        )
    assert r.status_code == 200
    card = r.json()
    assert card["action"] == "create_reservation"
    assert card["proposal_id"]
    assert card["fields"]
    assert card["expires_at"]

    pending = await store.take(card["proposal_id"], user_id="u1")
    assert pending.payload["customerName"] == "김미영"
    assert pending.payload["date"] == "2026-05-26"


async def test_ocr_unreadable_image_returns_422():
    app = _ocr_app(_VisionModel("이미지를 못 읽었어요"), PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600))
    async with _client(app) as c:
        r = await c.post(
            "/ocr/reservation",
            json={"image_url": "https://img.example/bad.png"},
            headers={"Authorization": "Bearer jwt"},
        )
    assert r.status_code == 422


async def test_ocr_requires_auth():
    app = _ocr_app(_VisionModel("{}"), PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600))
    async with _client(app) as c:
        r = await c.post("/ocr/reservation", json={"image_url": "https://img.example/x.png"})
    assert r.status_code == 401


def _confirm_app(store, backend):
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_pending_store] = lambda: store
    app.dependency_overrides[get_backend_client] = lambda: backend
    return app


def _pending() -> PendingWrite:
    return PendingWrite(
        id="prop-1",
        action="create_reservation",
        payload={"date": "2026-05-26", "customerName": "김미영", "title": "장미 다발", "amount": 30000},
        summary="5/26 김미영 장미 다발",
    )


@respx.mock
async def test_confirm_executes_write_and_is_one_shot():
    respx.post("http://backend.test/reservations").mock(return_value=httpx.Response(200, json={"id": "r1"}))
    store = PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)
    await store.save(_pending(), user_id="u1")
    backend = BackendClient("http://backend.test", timeout=5.0)
    app = _confirm_app(store, backend)

    async with _client(app) as c:
        r = await c.post("/confirm", json={"proposal_id": "prop-1"}, headers={"Authorization": "Bearer jwt"})
        assert r.status_code == 200
        assert r.json()["result"]["id"] == "r1"
        # 1회성 — 재확인은 404
        r2 = await c.post("/confirm", json={"proposal_id": "prop-1"}, headers={"Authorization": "Bearer jwt"})
        assert r2.status_code == 404
    await backend.aclose()


async def test_confirm_wrong_owner_returns_403():
    store = PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)
    await store.save(_pending(), user_id="owner")  # u1 아님
    backend = BackendClient("http://backend.test", timeout=5.0)
    app = _confirm_app(store, backend)
    async with _client(app) as c:
        r = await c.post("/confirm", json={"proposal_id": "prop-1"}, headers={"Authorization": "Bearer jwt"})
    assert r.status_code == 403
    await backend.aclose()


async def test_confirm_missing_returns_404():
    backend = BackendClient("http://backend.test", timeout=5.0)
    app = _confirm_app(PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600), backend)
    async with _client(app) as c:
        r = await c.post("/confirm", json={"proposal_id": "nope"}, headers={"Authorization": "Bearer jwt"})
    assert r.status_code == 404
    await backend.aclose()
