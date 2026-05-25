"""SPEC-AI-003 리뷰 반영(쓰기 경로 보안/견고성) 회귀 테스트."""

import json
import logging

import httpx
import pytest
import respx
from fakeredis import FakeAsyncRedis
from langchain_core.messages import AIMessage

from app.agents.vision import VisionExtractionError, extract_reservation_draft
from app.api.deps import (
    get_authenticator,
    get_backend_client,
    get_chat_model,
    get_pending_store,
    get_usage_limiter,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.confirm.executor import execute
from app.confirm.store import PendingWriteStore
from app.main import create_app
from app.session.models import PendingWrite


class _VisionModel:
    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return AIMessage(content=self._content)


class _FakeAuth:
    async def authenticate(self, jwt: str) -> RequestContext:
        return RequestContext(user_id="u1", jwt=jwt)


class _FakeUsage:
    async def enforce(self, user_id: str) -> int:
        return 1


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# --- 비전 추출 검증 강화 ---
async def test_vision_rejects_extra_fields():
    # LLM이 주입한 여분 필드(예: userId) → 거부
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


# --- 쓰기 멱등성: POST는 5xx에 재시도하지 않는다 ---
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


# --- 확인 실행 감사 로그에 payload(마스킹) 포함 ---
@respx.mock
async def test_confirm_audits_masked_payload(caplog):
    respx.post("http://backend.test/reservations").mock(return_value=httpx.Response(200, json={"id": "r1"}))
    store = PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)
    pending = PendingWrite(
        id="prop-1",
        action="create_reservation",
        payload={"customerName": "김미영", "customerPhone": "010-1234-5678", "date": "2026-05-26"},
        summary="s",
    )
    await store.save(pending, user_id="u1")
    backend = BackendClient("http://backend.test", timeout=5.0)
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_pending_store] = lambda: store
    app.dependency_overrides[get_backend_client] = lambda: backend

    with caplog.at_level(logging.INFO, logger="flori.audit"):
        async with _client(app) as c:
            r = await c.post("/confirm", json={"proposal_id": "prop-1"}, headers={"Authorization": "Bearer jwt"})
    assert r.status_code == 200
    events = [json.loads(rec.getMessage()) for rec in caplog.records]
    write_ev = next(e for e in events if e.get("event") == "write_executed")
    # payload가 기록되되 PII는 마스킹
    assert write_ev["payload"]["customerName"] == "김**"
    assert write_ev["payload"]["customerPhone"] == "010-****-5678"
    await backend.aclose()


# --- SSRF: 사설/메타데이터 URL 차단 ---
async def test_ocr_rejects_private_image_url():
    # 추출이 성공할 유효 JSON을 주어, 422가 오직 SSRF URL 검증 때문임을 보장
    valid_model = _VisionModel('{"customer_name":"a","date":"2026-05-26","title":"t"}')
    app = create_app()
    app.dependency_overrides[get_authenticator] = lambda: _FakeAuth()
    app.dependency_overrides[get_usage_limiter] = lambda: _FakeUsage()
    app.dependency_overrides[get_chat_model] = lambda: valid_model
    app.dependency_overrides[get_pending_store] = lambda: PendingWriteStore(FakeAsyncRedis(), ttl_seconds=600)
    async with _client(app) as c:
        for bad in ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/x", "file:///etc/passwd"]:
            r = await c.post("/ocr/reservation", json={"image_url": bad}, headers={"Authorization": "Bearer jwt"})
            assert r.status_code == 422, bad
