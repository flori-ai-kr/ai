"""AI 행위 감사 로깅. 모든 행위를 구조화 JSON으로 남기되 PII는 마스킹한다."""

import json
import logging
from typing import Any

_logger = logging.getLogger("flori.audit")

# 마스킹 대상 키 → 마스킹 함수
_PHONE_KEYS = {"customer_phone", "phone"}
_NAME_KEYS = {"customer_name", "name"}


def mask_phone(value: str) -> str:
    """앞 3자리·뒤 4자리만 남기고 가운데 숫자를 마스킹(구분자 보존)."""
    digits = [c for c in value if c.isdigit()]
    total = len(digits)
    out = []
    idx = 0
    for c in value:
        if c.isdigit():
            if idx < 3 or idx >= total - 4:
                out.append(c)
            else:
                out.append("*")
            idx += 1
        else:
            out.append(c)
    return "".join(out)


def mask_name(value: str) -> str:
    """첫 글자만 남기고 나머지를 마스킹."""
    if len(value) <= 1:
        return value
    return value[0] + "*" * (len(value) - 1)


def _mask(key: str, value: Any) -> Any:
    if key in _PHONE_KEYS and isinstance(value, str):
        return mask_phone(value)
    if key in _NAME_KEYS and isinstance(value, str):
        return mask_name(value)
    return value


def audit_event(event: str, *, user_id: str | None = None, **fields: Any) -> None:
    """감사 이벤트 1건을 구조화 JSON으로 기록한다."""
    payload: dict[str, Any] = {"event": event}
    if user_id is not None:
        payload["user_id"] = user_id
    for key, value in fields.items():
        payload[key] = _mask(key, value)
    _logger.info(json.dumps(payload, ensure_ascii=False))
