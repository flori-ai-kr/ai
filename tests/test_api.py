import httpx

from app.api.deps import get_authenticator, get_usage_limiter
from app.backend.auth import AuthError, RequestContext
from app.main import create_app


class _FakeAuth:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def authenticate(self, jwt: str) -> RequestContext:
        if self._fail:
            raise AuthError("bad")
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_health_is_public_and_ok():
    async with _client(create_app()) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "flori-ai"}


async def test_protected_route_rejects_missing_token():
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    async with _client(app) as c:
        r = await c.get("/whoami")
    assert r.status_code == 401


async def test_protected_route_accepts_valid_jwt():
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    async with _client(app) as c:
        r = await c.get("/whoami", headers={"Authorization": "Bearer good-jwt"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "u1"


async def test_protected_route_rejects_invalid_jwt():
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth(fail=True)
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    async with _client(app) as c:
        r = await c.get("/whoami", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401
