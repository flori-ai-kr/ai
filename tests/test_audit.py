import json
import logging

from app.core.audit import audit_event, mask_name, mask_phone


def test_mask_phone_keeps_last_four():
    assert mask_phone("010-1234-5678") == "010-****-5678"
    assert mask_phone("01012345678") == "010****5678"


def test_mask_name_keeps_first_char():
    assert mask_name("김미영") == "김**"
    assert mask_name("이순신") == "이**"
    assert mask_name("김") == "김"


def test_audit_event_emits_structured_json_with_masked_pii(caplog):
    with caplog.at_level(logging.INFO, logger="flori.audit"):
        audit_event(
            "reservation_proposed",
            user_id="u1",
            customer_name="김미영",
            customer_phone="010-1234-5678",
            amount=30000,
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].getMessage())
    assert payload["event"] == "reservation_proposed"
    assert payload["user_id"] == "u1"
    assert payload["customer_phone"] == "010-****-5678"
    assert payload["customer_name"] == "김**"
    assert payload["amount"] == 30000


def test_audit_event_redacts_secret_keys(caplog):
    with caplog.at_level(logging.INFO, logger="flori.audit"):
        audit_event("tool_call", user_id="u1", jwt="eyJhbGci.secret", token="abc", password="pw")
    payload = json.loads(caplog.records[0].getMessage())
    assert payload["jwt"] == "[REDACTED]"
    assert payload["token"] == "[REDACTED]"
    assert payload["password"] == "[REDACTED]"
