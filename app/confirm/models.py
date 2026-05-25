"""쓰기 제안(human-in-loop) 모델. ConfirmationCard는 모바일 앱과 공유하는 계약."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ReservationDraft(BaseModel):
    """비전 추출 결과 — 예약 후보(제안). 확인 전까지 백엔드에 쓰지 않는다.

    extra='forbid': LLM이 주입한 여분 필드(userId 등)가 payload로 새는 것을 차단.
    date/time/amount는 포맷·범위 검증 — 인젝션/hallucination 값이 백엔드로 가지 않게.
    """

    model_config = ConfigDict(extra="forbid")

    customer_name: str
    customer_phone: str | None = None
    date: str  # YYYY-MM-DD
    time: str | None = None  # HH:MM
    title: str  # 품목/제목 (예: "장미 다발")
    amount: int | None = Field(default=None, ge=0)

    @field_validator("date")
    @classmethod
    def _validate_date(cls, v: str) -> str:
        if not _DATE_RE.fullmatch(v):
            raise ValueError(f"date must be 'YYYY-MM-DD', got: {v!r}")
        return v

    @field_validator("time")
    @classmethod
    def _validate_time(cls, v: str | None) -> str | None:
        if v is not None and not _TIME_RE.fullmatch(v):
            raise ValueError(f"time must be 'HH:MM', got: {v!r}")
        return v


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
