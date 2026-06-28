"""마케팅 채널 전략. v1은 blog만 등록 — 인스타·스레드는 파일 추가만으로 확장."""

from app.agents.marketing.channels.base import Channel
from app.agents.marketing.channels.blog import BlogChannel

# 채널 레지스트리 — 엔드포인트가 channel 이름으로 디스패치한다.
CHANNELS: dict[str, Channel] = {
    "blog": BlogChannel(),
}


def get_channel(name: str) -> Channel:
    channel = CHANNELS.get(name)
    if channel is None:
        raise KeyError(f"unknown marketing channel: {name!r} (available: {list(CHANNELS)})")
    return channel


__all__ = ["CHANNELS", "Channel", "get_channel"]
