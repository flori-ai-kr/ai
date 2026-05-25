import httpx
import pytest
import respx
from fakeredis import FakeAsyncRedis

from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.confirm.executor import execute
from app.confirm.store import PendingNotFound, PendingWriteStore
from app.session.models import PendingWrite


def _pending() -> PendingWrite:
    return PendingWrite(
        id="prop-1",
        action="create_reservation",
        payload={"date": "2026-05-26", "customerName": "김미영", "title": "장미 다발", "amount": 30000},
        summary="5/26 김미영 장미 다발 예약",
    )


def _store() -> PendingWriteStore:
    return PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)


async def test_save_then_take_returns_pending_once():
    store = _store()
    await store.save(_pending(), user_id="u1")
    taken = await store.take("prop-1", user_id="u1")
    assert taken.action == "create_reservation"
    assert taken.payload["customerName"] == "김미영"
    # 1회성 — 두 번째는 없음
    with pytest.raises(PendingNotFound):
        await store.take("prop-1", user_id="u1")


async def test_take_missing_raises_not_found():
    with pytest.raises(PendingNotFound):
        await _store().take("nope", user_id="u1")


async def test_take_wrong_owner_raises_permission_and_keeps_pending():
    store = _store()
    await store.save(_pending(), user_id="owner")
    with pytest.raises(PermissionError):
        await store.take("prop-1", user_id="intruder")
    # 소유자 위반 시 삭제되지 않아야 함
    taken = await store.take("prop-1", user_id="owner")
    assert taken.id == "prop-1"


@respx.mock
async def test_execute_create_reservation_posts_with_jwt():
    route = respx.post("http://backend.test/reservations").mock(
        return_value=httpx.Response(200, json={"id": "r1", "date": "2026-05-26"})
    )
    client = BackendClient("http://backend.test", timeout=5.0)
    ctx = RequestContext(user_id="u1", jwt="jwt-xyz")
    result = await execute(client, ctx, _pending())

    assert result == {"id": "r1", "date": "2026-05-26"}
    assert route.calls.last.request.headers["Authorization"] == "Bearer jwt-xyz"
    import json as _json

    sent = _json.loads(route.calls.last.request.content)
    assert sent["customerName"] == "김미영"
    await client.aclose()


async def test_execute_unknown_action_raises():
    client = BackendClient("http://backend.test", timeout=5.0)
    ctx = RequestContext(user_id="u1", jwt="j")
    bad = PendingWrite(id="p", action="delete_everything", payload={}, summary="")
    with pytest.raises(ValueError):
        await execute(client, ctx, bad)
    await client.aclose()
