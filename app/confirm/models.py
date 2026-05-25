"""쓰기 제안(human-in-loop) 모델. ConfirmationCard는 모바일 앱과 공유하는 계약."""

from pydantic import BaseModel, Field


class ReservationDraft(BaseModel):
    """비전 추출 결과 — 예약 후보(제안). 확인 전까지 백엔드에 쓰지 않는다."""

    customer_name: str
    customer_phone: str | None = None
    date: str  # YYYY-MM-DD
    time: str | None = None  # HH:MM
    title: str  # 품목/제목 (예: "장미 다발")
    amount: int | None = None


class ConfirmationField(BaseModel):
    label: str
    value: str


class ConfirmationCard(BaseModel):
    """앱이 렌더하는 확인 카드 계약. 사용자가 확인하면 proposal_id로 /confirm 호출."""

    proposal_id: str
    action: str  # 예: "create_reservation"
    summary: str
    fields: list[ConfirmationField] = Field(default_factory=list)
    expires_at: str  # ISO 8601 (UTC)
