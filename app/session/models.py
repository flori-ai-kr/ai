"""대화 세션 모델. 전송계층(HTTP/SSE → WS/WebRTC)과 독립.

채널 무관(텍스트/음성 공통)하게 session_id + 턴으로 추상화한다. C1→C2 전환 시
전송계층만 교체하고 이 모델·스토어는 재사용한다.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant", "system"]
Kind = Literal["text", "image", "audio"]


class Turn(BaseModel):
    role: Role
    text: str
    kind: Kind = "text"


class PendingWrite(BaseModel):
    """쓰기 제안(human-in-loop). 확인 카드 → /confirm 시 실행. 자리만 예약(B에서 사용)."""

    id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class Session(BaseModel):
    session_id: str
    user_id: str
    lang: str = "ko"
    turns: list[Turn] = Field(default_factory=list)
    pending_writes: list[PendingWrite] = Field(default_factory=list)
