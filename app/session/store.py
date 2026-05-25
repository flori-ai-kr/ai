"""Redis 기반 대화 세션 스토어. session_id 단위 직렬화(JSON) + TTL."""

from redis.asyncio import Redis

from app.session.models import Session, Turn

_KEY_PREFIX = "flori:session"


class SessionStore:
    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}:{session_id}"

    async def get(self, session_id: str) -> Session | None:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return Session.model_validate_json(raw)

    async def save(self, session: Session) -> None:
        await self._redis.set(
            self._key(session.session_id),
            session.model_dump_json(),
            ex=self._ttl,
        )

    async def get_or_create(self, session_id: str, user_id: str) -> Session:
        existing = await self.get(session_id)
        if existing is not None:
            return existing
        session = Session(session_id=session_id, user_id=user_id)
        await self.save(session)
        return session

    async def append_turn(self, session_id: str, turn: Turn) -> Session:
        session = await self.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        session.turns.append(turn)
        await self.save(session)
        return session
