"""OCR→예약 추출 — 이미지에서 예약 후보(draft)를 추출해 반환한다.

게이트웨이 뒤 stateless: 여기서는 저장하지 않는다. 추출 결과(draft)만 돌려주고,
게이트웨이가 제안(ai_write_proposal)으로 보관 → 사용자가 확인(/ai/confirm)하면 게이트웨이가 예약을 생성한다.
"""

import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, field_validator

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.api.deps import get_chat_model, get_request_context, get_settings
from app.backend.auth import RequestContext
from app.core.config import Settings

router = APIRouter()


def _is_blocked_host(host: str) -> bool:
    """사설/루프백/링크로컬/예약 IP 리터럴·localhost 차단(SSRF 1차 방어, DNS 리졸브는 미수행)."""
    if not host or host.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # 도메인명 — IP 리터럴 기반 사설 접근만 차단
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


class OcrReservationRequest(BaseModel):
    image_url: str = Field(..., max_length=2000)
    model: str | None = None  # 게이트웨이 힌트(현재는 ai-server 설정 모델 사용)

    @field_validator("image_url")
    @classmethod
    def _no_ssrf(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("image_url must be an http(s) URL")
        if _is_blocked_host(parsed.hostname or ""):
            raise ValueError("image_url must not target a private/loopback address")
        return v


class DraftOut(BaseModel):
    """추출된 예약 초안(snake_case — 게이트웨이 계약)."""

    customer_name: str | None = None
    customer_phone: str | None = None
    date: str | None = None
    time: str | None = None
    title: str | None = None
    amount: int | None = None


class OcrExtractResponse(BaseModel):
    draft: DraftOut
    model: str


@router.post("/ocr/reservation", response_model=OcrExtractResponse)
async def ocr_reservation(
    req: OcrReservationRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_chat_model),
    settings: Settings = Depends(get_settings),
) -> OcrExtractResponse:
    try:
        draft = await extract_reservation_draft(model, req.image_url)
    except VisionExtractionError:
        raise HTTPException(status_code=422, detail="이미지에서 예약 정보를 읽지 못했어요.") from None

    return OcrExtractResponse(
        draft=DraftOut(
            customer_name=draft.customer_name,
            customer_phone=draft.customer_phone,
            date=draft.date,
            time=draft.time,
            title=draft.title,
            amount=draft.amount,
        ),
        model=settings.llm_model,
    )
