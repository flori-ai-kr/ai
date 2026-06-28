import pytest
from langchain_core.messages import AIMessage

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.confirm.models import ReservationDraft


class _VisionModel:
    def __init__(self, content: str) -> None:
        self._content = content
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return AIMessage(content=self._content)


class _StructuredVisionModel:
    """with_structured_output을 지원하는 모델 — 스키마 강제 경로 검증용."""

    def __init__(self, draft: ReservationDraft) -> None:
        self._draft = draft
        self.requested_schema = None

    def with_structured_output(self, schema):
        self.requested_schema = schema
        return self

    async def ainvoke(self, messages):
        return self._draft


class _StructuredFailsModel:
    """구조화 출력은 실패하고 자유형 ainvoke로 폴백되는 모델."""

    def __init__(self, raw_content: str) -> None:
        self._raw = raw_content

    def with_structured_output(self, schema):
        class _Failing:
            async def ainvoke(self, messages):
                raise RuntimeError("structured output not supported")

        return _Failing()

    async def ainvoke(self, messages):
        return AIMessage(content=self._raw)


async def test_extract_parses_plain_json():
    model = _VisionModel(
        '{"customer_name":"김미영","customer_phone":"010-1234-5678",'
        '"date":"2026-05-26","time":"14:00","title":"장미 다발","amount":30000}'
    )
    draft = await extract_reservation_draft(model, "https://img.example/x.png")
    assert draft.customer_name == "김미영"
    assert draft.customer_phone == "010-1234-5678"
    assert draft.date == "2026-05-26"
    assert draft.time == "14:00"
    assert draft.title == "장미 다발"
    assert draft.amount == 30000


async def test_extract_parses_code_fenced_json():
    model = _VisionModel('```json\n{"customer_name":"이순신","date":"2026-06-01","title":"꽃다발"}\n```')
    draft = await extract_reservation_draft(model, "url")
    assert draft.customer_name == "이순신"
    assert draft.customer_phone is None
    assert draft.amount is None


async def test_extract_invalid_response_raises():
    model = _VisionModel("죄송해요, 이미지를 읽지 못했어요.")
    with pytest.raises(VisionExtractionError):
        await extract_reservation_draft(model, "url")


async def test_extract_uses_structured_output_when_supported():
    draft = ReservationDraft(customer_name="홍길동", date="2026-07-01", title="안개꽃")
    model = _StructuredVisionModel(draft)
    result = await extract_reservation_draft(model, "https://img.example/z.png")
    assert result is draft
    assert model.requested_schema is ReservationDraft  # 스키마가 강제됨


async def test_extract_falls_back_to_manual_parse_when_structured_unsupported():
    # 구조화 출력이 실패하면 자유형 응답 + 수제 JSON 파싱으로 폴백한다.
    model = _StructuredFailsModel('{"customer_name":"김철수","date":"2026-08-02","title":"튤립"}')
    draft = await extract_reservation_draft(model, "url")
    assert draft.customer_name == "김철수"
    assert draft.title == "튤립"


async def test_extract_sends_image_to_model():
    model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t"}')
    await extract_reservation_draft(model, "https://img.example/y.png")
    # 멀티모달 메시지에 이미지가 실려야 한다
    serialized = str(model.last_messages)
    assert "https://img.example/y.png" in serialized
