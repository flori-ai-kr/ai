"""헬스체크 — 인증·외부 의존 없음(liveness)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "flori-ai"}
