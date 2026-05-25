"""백엔드(Spring REST) 도구 클라이언트.

핵심 책임: 유저 JWT를 ``Authorization: Bearer`` 로 **그대로 전달**(패스스루)하고,
타임아웃·재시도와 상태코드→예외 매핑을 일관되게 처리한다. 멀티테넌시 격리는
이 JWT를 받은 백엔드(TenantContext)가 강제하므로, AI 서버는 격리 로직을 갖지 않는다.
"""

from typing import Any

import httpx


class BackendError(Exception):
    """백엔드 호출 실패. 4xx/5xx 또는 전송 오류."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendAuthError(BackendError):
    """백엔드가 401을 반환 — JWT 무효/만료."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._max_retries = max_retries

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        jwt: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {jwt}"}
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.request(method, path, headers=headers, params=params, json=json)
            except httpx.TransportError as exc:  # 네트워크 오류 → 재시도
                last_exc = exc
                if attempt < self._max_retries:
                    continue
                raise BackendError(f"backend transport error: {exc}") from exc

            if resp.status_code == 401:
                raise BackendAuthError("backend rejected JWT (401)", status_code=401)
            if resp.status_code >= 500 and attempt < self._max_retries:
                continue  # 일시적 서버 오류 → 재시도
            if resp.status_code >= 400:
                # 메시지엔 상태코드만 — 내부 경로/메서드는 노출하지 않는다.
                raise BackendError(
                    f"backend error {resp.status_code}",
                    status_code=resp.status_code,
                )
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()

        raise BackendError(f"backend request failed after retries: {last_exc}")  # pragma: no cover

    async def get(self, path: str, *, jwt: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, jwt=jwt, params=params)

    async def post(self, path: str, *, jwt: str, json: dict[str, Any] | None = None) -> Any:
        return await self.request("POST", path, jwt=jwt, json=json)
