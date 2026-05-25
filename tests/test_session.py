from fakeredis import FakeAsyncRedis

from app.session.models import Session, Turn
from app.session.store import SessionStore


def _store() -> SessionStore:
    return SessionStore(FakeAsyncRedis(), ttl_seconds=3600)


async def test_get_or_create_new_session():
    s = await _store().get_or_create("sess-1", "u1")
    assert s.session_id == "sess-1"
    assert s.user_id == "u1"
    assert s.turns == []
    assert s.lang == "ko"


async def test_get_missing_returns_none():
    assert await _store().get("does-not-exist") is None


async def test_save_and_get_roundtrip():
    store = _store()
    s = await store.get_or_create("sess-1", "u1")
    s.turns.append(Turn(role="user", text="이번 달 매출 왜 떨어졌어?"))
    await store.save(s)

    loaded = await store.get("sess-1")
    assert loaded is not None
    assert loaded.user_id == "u1"
    assert loaded.turns[0].text == "이번 달 매출 왜 떨어졌어?"
    assert loaded.turns[0].role == "user"


async def test_append_turn_persists():
    store = _store()
    await store.get_or_create("s", "u1")
    updated = await store.append_turn("s", Turn(role="assistant", text="객단가가 낮아졌어요"))
    assert len(updated.turns) == 1

    reloaded = await store.get("s")
    assert reloaded is not None
    assert len(reloaded.turns) == 1
    assert isinstance(reloaded, Session)
