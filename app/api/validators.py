"""공용 입력 검증 타입."""

import ipaddress
import re
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator

# Redis 키 등으로 쓰이는 식별자 — 영숫자/-/_ 만 허용(키 네임스페이스 오염 방지).
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_blocked_host(host: str) -> bool:
    """사설/루프백/링크로컬/예약 IP 리터럴·localhost 차단(SSRF 1차 방어, DNS 리졸브는 미수행)."""
    if not host or host.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # 도메인명 — IP 리터럴 기반 사설 접근만 차단
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def validate_http_image_url(v: str) -> str:
    """이미지 URL을 http(s) + 비사설로 검증(SSRF 가드). ocr·marketing 공용."""
    parsed = urlparse(v)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("image url must be an http(s) URL")
    if is_blocked_host(parsed.hostname or ""):
        raise ValueError("image url must not target a private/loopback address")
    return v


def is_safe_id(v: str) -> bool:
    """식별자 형식 검사 (WS 등 Pydantic 밖 경로에서 사용)."""
    return bool(_SAFE_ID_RE.fullmatch(v))


def _validate_safe_id(v: str) -> str:
    if not is_safe_id(v):
        raise ValueError("id must be alphanumeric, '-' or '_', up to 64 chars")
    return v


SafeId = Annotated[str, AfterValidator(_validate_safe_id)]
