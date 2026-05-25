import pytest
from fakeredis import FakeAsyncRedis

from app.core.usage import UsageCapExceeded, UsageLimiter


async def test_usage_under_cap_passes():
    limiter = UsageLimiter(FakeAsyncRedis(), cap=3)
    assert await limiter.enforce("u1") == 1
    assert await limiter.enforce("u1") == 2
    assert await limiter.enforce("u1") == 3


async def test_usage_over_cap_raises():
    limiter = UsageLimiter(FakeAsyncRedis(), cap=2)
    await limiter.enforce("u1")
    await limiter.enforce("u1")
    with pytest.raises(UsageCapExceeded):
        await limiter.enforce("u1")


async def test_usage_isolated_per_user():
    limiter = UsageLimiter(FakeAsyncRedis(), cap=1)
    await limiter.enforce("u1")
    # 다른 유저는 영향받지 않는다
    assert await limiter.enforce("u2") == 1
