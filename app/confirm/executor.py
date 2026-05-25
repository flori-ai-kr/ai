"""확정된 쓰기 제안 실행. 에이전트 루프 밖 — 사용자가 확인(/confirm)했을 때만 호출된다.

JWT 패스스루로 백엔드 쓰기 엔드포인트를 호출한다(격리·권한은 백엔드가 강제).
"""

from typing import Any

from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.session.models import PendingWrite


async def execute(client: BackendClient, ctx: RequestContext, pending: PendingWrite) -> Any:
    if pending.action == "create_reservation":
        return await client.post("/reservations", jwt=ctx.jwt, json=pending.payload)
    raise ValueError(f"unknown write action: {pending.action}")
