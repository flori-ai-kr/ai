"""SPEC-AI-003 리뷰 반영(쓰기 경로 보안/견고성) 회귀 테스트.

쓰기 확인(/confirm)은 게이트웨이(Spring)가 소유한다 — ai-server는 추출(draft)만 한다.
여기서는 비전 추출 검증·쓰기 멱등성(executor)·OCR SSRF 가드를 회귀로 검증한다.
"""

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.api.deps import get_chat_model, get_request_context
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.confirm.executor import execute
from app.main import create_app
from app.session.models import PendingWrite


class _VisionModel:
    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return AIMessage(content=self._content)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# --- 비전 추출 검증 강화 ---
async def test_vision_rejects_extra_fields():
    model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t","userId":"other"}')
    with pytest.raises(VisionExtractionError):
        await extract_reservation_draft(model, "https://img/x.png")


async def test_vision_rejects_bad_date_format():
    model = _VisionModel('{"customer_name":"a","date":"2026/05/26","title":"t"}')
    with pytest.raises(VisionExtractionError):
        await extract_reservation_draft(model, "https://img/x.png")


async def test_vision_rejects_negative_amount():
    model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t","amount":-100}')
    with pytest.raises(VisionExtractionError):
        await extract_reservation_draft(model, "https://img/x.png")


# --- 쓰기 멱등성: POST는 5xx에 재시도하지 않는다 (executor는 게이트웨이 confirm에서도 재사용 가능) ---
@respx.mock
async def test_execute_does_not_retry_write_on_5xx():
    route = respx.post("http://backend.test/reservations").mock(return_value=httpx.Response(500))
    client = BackendClient("http://backend.test", timeout=5.0, max_retries=2)
    ctx = RequestContext(user_id="u1", jwt="j")
    pending = PendingWrite(id="p", action="create_reservation", payload={"date": "2026-05-26"}, summary="")
    from app.backend.client import BackendError

    with pytest.raises(BackendError):
        await execute(client, ctx, pending)
    assert route.call_count == 1  # 재시도 없음(중복 예약 방지)
    await client.aclose()


# --- SSRF: 사설/메타데이터 URL 차단 (OCR 추출 엔드포인트) ---
async def test_ocr_rejects_private_image_url():
    # 추출이 성공할 유효 JSON을 주어, 422가 오직 SSRF URL 검증 때문임을 보장
    valid_model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t"}')
    app = create_app()
    app.dependency_overrides[get_request_context] = lambda: RequestContext(user_id="u1", jwt="jwt")
    app.dependency_overrides[get_chat_model] = lambda: valid_model
    async with _client(app) as c:
        for bad in ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/x", "file:///etc/passwd"]:
            r = await c.post("/ocr/reservation", json={"image_url": bad})
            assert r.status_code == 422, bad
