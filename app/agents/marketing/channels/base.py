"""채널 전략 프로토콜 — 채널마다 프롬프트·출력스키마·후처리를 캡슐화한다."""

from typing import Protocol

from pydantic import BaseModel

from app.agents.marketing.schemas import BlogGenInput


class Channel(Protocol):
    """마케팅 채널 전략. 새 채널 = 이 프로토콜 구현 + 레지스트리 등록만."""

    name: str

    def output_schema(self) -> type[BaseModel]:
        """구조화 출력에 강제할 Pydantic 스키마."""
        ...

    def build_messages(self, gen_input: BlogGenInput) -> list:
        """LLM 메시지(system + multimodal human) 구성. 사용자 입력은 펜스로 격리."""
        ...

    def postprocess(self, draft: BaseModel, gen_input: BlogGenInput) -> BaseModel:
        """결정적 후처리(지시대명사 치환 등)."""
        ...
