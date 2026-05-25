"""OCR→예약 — 이미지에서 예약 후보를 추출해 확인 카드(human-in-loop)를 반환.

여기서는 백엔드에 쓰지 않는다. 카드를 확인(POST /confirm)해야 실제 예약이 생성된다.
"""

import ipaddress
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, field_validator

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.api.deps import get_chat_model, get_pending_store, get_request_context
from app.backend.auth import RequestContext
from app.confirm.models import ConfirmationCard, ConfirmationField, ReservationDraft
from app.confirm.store import PendingWriteStore
from app.session.models import PendingWrite

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

    @field_validator("image_url")
    @classmethod
    def _no_ssrf(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("image_url must be an http(s) URL")
        if _is_blocked_host(parsed.hostname or ""):
            raise ValueError("image_url must not target a private/loopback address")
        return v


def _draft_to_payload(draft: ReservationDraft) -> dict[str, Any]:
    """ReservationDraft → 백엔드 POST /reservations DTO(None은 생략)."""
    payload: dict[str, Any] = {
        "date": draft.date,
        "customerName": draft.customer_name,
        "title": draft.title,
        "amount": draft.amount or 0,
    }
    if draft.time:
        payload["time"] = draft.time
    if draft.customer_phone:
        payload["customerPhone"] = draft.customer_phone
    return payload


def _draft_to_fields(draft: ReservationDraft) -> list[ConfirmationField]:
    pairs = [
        ("고객", draft.customer_name),
        ("연락처", draft.customer_phone),
        ("날짜", draft.date),
        ("시간", draft.time),
        ("품목", draft.title),
        ("금액", f"{draft.amount:,}원" if draft.amount is not None else None),
    ]
    return [ConfirmationField(label=label, value=value) for label, value in pairs if value]


@router.post("/ocr/reservation", response_model=ConfirmationCard)
async def ocr_reservation(
    req: OcrReservationRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_chat_model),
    store: PendingWriteStore = Depends(get_pending_store),
) -> ConfirmationCard:
    try:
        draft = await extract_reservation_draft(model, req.image_url)
    except VisionExtractionError:
        raise HTTPException(status_code=422, detail="이미지에서 예약 정보를 읽지 못했어요.") from None

    proposal_id = uuid.uuid4().hex  # uuid4 = os.urandom 기반 CSPRNG — 추측 불가
    payload = _draft_to_payload(draft)
    when = f"{draft.date} {draft.time}" if draft.time else draft.date
    summary = f"{when} · {draft.customer_name} · {draft.title}"
    pending = PendingWrite(id=proposal_id, action="create_reservation", payload=payload, summary=summary)

    # expires_at은 저장(TTL)과 동일 출처로 — 카드 표시와 실제 만료의 불일치 방지.
    expires_at = (datetime.now(UTC) + timedelta(seconds=store.ttl_seconds)).isoformat()
    await store.save(pending, user_id=ctx.user_id)

    return ConfirmationCard(
        proposal_id=proposal_id,
        action="create_reservation",
        summary=summary,
        fields=_draft_to_fields(draft),
        expires_at=expires_at,
    )
