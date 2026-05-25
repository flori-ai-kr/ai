"""유저별 사용량 캡 (seam). Redis 일일 카운터로 호출 수를 제한한다.

정책 정교화(토큰/비용 기준, 구독 등급 연동)는 후속 SPEC. 여기서는 자리를 만든다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from redis.asyncio import Redis

_KST = ZoneInfo("Asia/Seoul")
_TTL_SECONDS = 60 * 60 * 48  # 2일 (일일 윈도우 + 여유)


class UsageCapExceeded(Exception):
    """일일 사용량 한도 초과."""


class UsageLimiter:
    def __init__(self, redis: Redis, cap: int, *, key_prefix: str = "flori:usage") -> None:
        self._redis = redis
        self._cap = cap
        self._prefix = key_prefix

    def _day_key(self, user_id: str) -> str:
        day = datetime.now(_KST).strftime("%Y%m%d")
        return f"{self._prefix}:{user_id}:{day}"

    async def enforce(self, user_id: str) -> int:
        """오늘 카운터를 1 증가시키고 현재 값을 반환. 한도 초과 시 예외."""
        key = self._day_key(user_id)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, _TTL_SECONDS)
        if count > self._cap:
            raise UsageCapExceeded(f"daily usage cap exceeded: {count} > {self._cap}")
        return count
