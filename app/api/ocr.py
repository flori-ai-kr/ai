"""OCR→예약 — 이미지에서 예약 후보를 추출해 확인 카드(human-in-loop)를 반환.

여기서는 백엔드에 쓰지 않는다. 카드를 확인(POST /confirm)해야 실제 예약이 생성된다.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.api.deps import get_chat_model, get_pending_store, get_request_context
from app.backend.auth import RequestContext
from app.confirm.models import ConfirmationCard, ConfirmationField, ReservationDraft
from app.confirm.store import PendingWriteStore
from app.core.config import get_settings
from app.session.models import PendingWrite

router = APIRouter()


class OcrReservationRequest(BaseModel):
    image_url: str = Field(..., max_length=2000)


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

    proposal_id = uuid.uuid4().hex
    payload = _draft_to_payload(draft)
    summary = f"{draft.date} {draft.time or ''} {draft.customer_name} · {draft.title}".strip()
    pending = PendingWrite(id=proposal_id, action="create_reservation", payload=payload, summary=summary)
    await store.save(pending, user_id=ctx.user_id)

    expires_at = (datetime.now(UTC) + timedelta(seconds=get_settings().pending_ttl_seconds)).isoformat()
    return ConfirmationCard(
        proposal_id=proposal_id,
        action="create_reservation",
        summary=summary,
        fields=_draft_to_fields(draft),
        expires_at=expires_at,
    )
