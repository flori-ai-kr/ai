import httpx
import pytest
import respx

from app.backend.client import BackendAuthError, BackendClient, BackendError


@respx.mock
async def test_forwards_user_jwt_and_returns_json():
    route = respx.get("http://backend.test/dashboard/month").mock(
        return_value=httpx.Response(200, json={"summary": {"total": 100}})
    )
    client = BackendClient("http://backend.test", timeout=5.0)
    data = await client.get("/dashboard/month", jwt="user-jwt-xyz", params={"month": "2026-05"})

    assert data == {"summary": {"total": 100}}
    assert route.calls.last.request.headers["Authorization"] == "Bearer user-jwt-xyz"
    await client.aclose()


@respx.mock
async def test_maps_401_to_auth_error():
    respx.get("http://backend.test/me").mock(return_value=httpx.Response(401))
    client = BackendClient("http://backend.test", timeout=5.0)
    with pytest.raises(BackendAuthError):
        await client.get("/me", jwt="bad")
    await client.aclose()


@respx.mock
async def test_maps_4xx_to_backend_error_with_status():
    respx.post("http://backend.test/reservations").mock(return_value=httpx.Response(422, json={"message": "bad"}))
    client = BackendClient("http://backend.test", timeout=5.0)
    with pytest.raises(BackendError) as exc:
        await client.post("/reservations", jwt="t", json={"date": "x"})
    assert exc.value.status_code == 422
    await client.aclose()


@respx.mock
async def test_retries_on_5xx_then_succeeds():
    route = respx.get("http://backend.test/sales").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"items": []})]
    )
    client = BackendClient("http://backend.test", timeout=5.0, max_retries=2)
    data = await client.get("/sales", jwt="t")

    assert data == {"items": []}
    assert route.call_count == 2
    await client.aclose()
