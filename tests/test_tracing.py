import pytest

from app.observability.tracing import observe


@observe
async def _bare(x: int) -> int:
    return x * 2


@observe(name="named-op")
async def _named(x: int) -> int:
    if x < 0:
        raise ValueError("negative")
    return x + 1


async def test_observe_bare_is_noop_passthrough():
    # Langfuse 미설정 — 데코레이터가 동작을 그대로 보존
    assert await _bare(3) == 6


async def test_observe_named_preserves_return_and_exceptions():
    assert await _named(1) == 2
    with pytest.raises(ValueError):
        await _named(-1)
