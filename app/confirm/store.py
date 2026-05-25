"""쓰기 제안(PendingWrite) 저장소. Redis에 proposal_id 키로 user_id 바인딩 + TTL.

위변조/재사용 방지: 소유자 검증 + 1회성(take 시 삭제). 만료는 TTL.
"""

import json

from redis.asyncio import Redis

from app.session.models import PendingWrite

_KEY_PREFIX = "flori:pending"


class PendingNotFound(Exception):
    """proposal이 없거나 만료됨."""


class PendingWriteStore:
    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, proposal_id: str) -> str:
        return f"{_KEY_PREFIX}:{proposal_id}"

    async def save(self, pending: PendingWrite, *, user_id: str) -> None:
        record = {"user_id": user_id, "pending": pending.model_dump()}
        await self._redis.set(self._key(pending.id), json.dumps(record, ensure_ascii=False), ex=self._ttl)

    async def take(self, proposal_id: str, *, user_id: str) -> PendingWrite:
        """소유자 검증 후 반환하고 삭제(1회성). 없으면 PendingNotFound, 타 유저면 PermissionError."""
        raw = await self._redis.get(self._key(proposal_id))
        if raw is None:
            raise PendingNotFound(proposal_id)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        record = json.loads(raw)
        if record.get("user_id") != user_id:
            # 소유자 위반 — 삭제하지 않고 거부(타 유저가 남의 proposal을 소진시키지 못하게)
            raise PermissionError(f"proposal {proposal_id} is not owned by the caller")
        await self._redis.delete(self._key(proposal_id))
        return PendingWrite(**record["pending"])
