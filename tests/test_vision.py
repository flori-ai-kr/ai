import pytest
from langchain_core.messages import AIMessage

from app.agents.vision import VisionExtractionError, extract_reservation_draft


class _VisionModel:
    def __init__(self, content: str) -> None:
        self._content = content
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return AIMessage(content=self._content)


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


async def test_extract_sends_image_to_model():
    model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t"}')
    await extract_reservation_draft(model, "https://img.example/y.png")
    # 멀티모달 메시지에 이미지가 실려야 한다
    serialized = str(model.last_messages)
    assert "https://img.example/y.png" in serialized
