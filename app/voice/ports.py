"""STT/TTS 프로바이더 Port. 프로바이더 중립 — 구현(AWS 등)은 어댑터로 주입, C에서 교체 가능."""

from typing import Protocol, runtime_checkable


class VoiceProviderError(Exception):
    """STT/TTS 프로바이더 호출 실패. 내부(AWS) 디테일은 노출하지 않는다."""


@runtime_checkable
class SttProvider(Protocol):
    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        """오디오 바이트를 텍스트로 변환."""
        ...


@runtime_checkable
class TtsProvider(Protocol):
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        """텍스트를 음성으로 합성. (audio_bytes, content_type) 반환."""
        ...
