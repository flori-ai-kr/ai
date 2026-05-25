import httpx
import pytest
import respx

from app.backend.auth import Authenticator, AuthError
from app.backend.client import BackendClient


def _make_auth(*, ttl: int = 60, now_fn=None) -> tuple[Authenticator, BackendClient]:
    client = BackendClient("http://backend.test", timeout=5.0)
    return Authenticator(client, cache_ttl_seconds=ttl, now_fn=now_fn), client


@respx.mock
async def test_authenticate_returns_request_context():
    respx.get("http://backend.test/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "email": "a@b.com", "name": "사장"})
    )
    auth, client = _make_auth()
    ctx = await auth.authenticate("jwt-1")
    assert ctx.user_id == "u1"
    assert ctx.jwt == "jwt-1"
    await client.aclose()


@respx.mock
async def test_authenticate_caches_within_ttl():
    route = respx.get("http://backend.test/me").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    auth, client = _make_auth(ttl=60)
    await auth.authenticate("jwt-1")
    await auth.authenticate("jwt-1")
    assert route.call_count == 1  # 두 번째는 캐시 히트
    await client.aclose()


@respx.mock
async def test_authenticate_invalid_jwt_raises():
    respx.get("http://backend.test/me").mock(return_value=httpx.Response(401))
    auth, client = _make_auth()
    with pytest.raises(AuthError):
        await auth.authenticate("bad")
    await client.aclose()


@respx.mock
async def test_cache_expires_after_ttl():
    route = respx.get("http://backend.test/me").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    clock = {"t": 1000.0}
    auth, client = _make_auth(ttl=60, now_fn=lambda: clock["t"])
    await auth.authenticate("jwt-1")  # call 1
    clock["t"] += 30
    await auth.authenticate("jwt-1")  # cache hit
    clock["t"] += 40  # 70 > 60 → 만료
    await auth.authenticate("jwt-1")  # call 2
    assert route.call_count == 2
    await client.aclose()
