import httpx

from app.api.deps import get_request_context
from app.backend.auth import RequestContext
from app.main import create_app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_health_is_public_and_ok():
    async with _client(create_app()) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "flori-ai"}


async def test_protected_route_rejects_missing_internal_key():
    # 게이트웨이 신뢰 인증: X-Internal-Key 없으면 401.
    async with _client(create_app()) as c:
        r = await c.get("/whoami")
    assert r.status_code == 401


async def test_protected_route_rejects_wrong_internal_key():
    async with _client(create_app()) as c:
        r = await c.get("/whoami", headers={"X-Internal-Key": "wrong", "X-User-Id": "u1"})
    assert r.status_code == 401


async def test_protected_route_accepts_gateway_context():
    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    async with _client(app) as c:
        r = await c.get("/whoami")
    assert r.status_code == 200
    assert r.json()["user_id"] == "u1"
