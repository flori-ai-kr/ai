"""관측성 seam — Langfuse @observe (v1 선택, no-op 폴백).

Langfuse가 설치·설정된 경우에만 트레이싱을 위임하고, 아니면 함수를 그대로 반환(no-op)한다.
키 부재/오류가 본 기능을 막지 않는다(fail-open). 실제 Langfuse 연동은 env로 켠다.
"""

import os
from collections.abc import Callable
from typing import Any


def _tracing_enabled() -> bool:
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return False
    try:
        import langfuse  # noqa: F401
    except ImportError:
        return False
    return True


def observe(func: Callable[..., Any] | None = None, *, name: str | None = None) -> Any:
    """`@observe` 또는 `@observe(name=...)`. 미설정 시 no-op 패스스루."""

    def _decorate(f: Callable[..., Any]) -> Callable[..., Any]:
        if not _tracing_enabled():
            return f
        from langfuse import observe as _lf_observe  # pragma: no cover - infra

        return _lf_observe(name=name)(f) if name else _lf_observe(f)  # pragma: no cover - infra

    if func is not None:
        return _decorate(func)
    return _decorate
