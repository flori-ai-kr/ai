"""유저 JWT 경량 검증. 서명키를 AI 서버에 두지 않고 백엔드 ``/me`` 인트로스펙션으로
유효성·userId를 확인한다(짧은 캐시). 검증한 JWT는 그대로 도구 호출에 패스스루된다.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.backend.client import BackendAuthError, BackendClient, BackendError


class AuthError(Exception):
    """JWT 검증 실패 — 무효/만료 또는 백엔드 거부."""


@dataclass(frozen=True)
class RequestContext:
    """인증된 요청의 단일 출처. 도구는 여기 담긴 ``jwt``를 백엔드에 패스스루한다."""

    user_id: str
    jwt: str


class Authenticator:
    def __init__(
        self,
        backend: BackendClient,
        *,
        cache_ttl_seconds: int,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self._backend = backend
        self._ttl = cache_ttl_seconds
        self._now = now_fn or time.monotonic
        self._cache: dict[str, tuple[str, float]] = {}  # jwt -> (user_id, expires_at)

    async def authenticate(self, jwt: str) -> RequestContext:
        now = self._now()
        cached = self._cache.get(jwt)
        if cached is not None and cached[1] > now:
            return RequestContext(user_id=cached[0], jwt=jwt)

        try:
            me = await self._backend.get("/me", jwt=jwt)
        except BackendAuthError as exc:
            self._cache.pop(jwt, None)
            raise AuthError("invalid or expired JWT") from exc
        except BackendError as exc:
            raise AuthError(f"auth introspection failed: {exc}") from exc

        user_id = me.get("id") if isinstance(me, dict) else None
        if not user_id:
            raise AuthError("/me response missing user id")

        self._cache[jwt] = (user_id, now + self._ttl)
        return RequestContext(user_id=user_id, jwt=jwt)
