"""공용 입력 검증 타입."""

import re
from typing import Annotated

from pydantic import AfterValidator

# Redis 키 등으로 쓰이는 식별자 — 영숫자/-/_ 만 허용(키 네임스페이스 오염 방지).
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_safe_id(v: str) -> str:
    if not _SAFE_ID_RE.fullmatch(v):
        raise ValueError("id must be alphanumeric, '-' or '_', up to 64 chars")
    return v


SafeId = Annotated[str, AfterValidator(_validate_safe_id)]
