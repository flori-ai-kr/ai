"""AWS STT/TTS 어댑터 — Transcribe(STT) + Polly(TTS).

Bedrock 스택과 동일 클라우드(IAM·자격은 env). 실제 AWS 호출은 인프라(범위 밖)에서 검증하고,
여기서는 Polly 호출 파라미터와 Transcribe transcript 수집 로직을 단위 검증한다.
"""

import asyncio
from typing import Any

import boto3
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

_AUDIO_CHUNK = 16 * 1024


class PollyTts:
    """AWS Polly TTS. 기본 한국어 음성 Seoyeon, mp3 출력."""

    def __init__(self, *, voice: str = "Seoyeon", region: str = "ap-northeast-2", client: Any = None) -> None:
        self._client = client or boto3.client("polly", region_name=region)
        self._voice = voice

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        def _call() -> bytes:
            resp = self._client.synthesize_speech(Text=text, VoiceId=self._voice, OutputFormat="mp3")
            return resp["AudioStream"].read()

        audio = await asyncio.to_thread(_call)
        return audio, "audio/mpeg"


class _TranscriptCollector(TranscriptResultStreamHandler):
    """스트림 이벤트에서 final 결과만 누적(partial 무시)."""

    def __init__(self, output_stream: Any) -> None:
        super().__init__(output_stream)
        self._parts: list[str] = []

    async def handle_transcript_event(self, transcript_event: TranscriptEvent) -> None:
        for result in transcript_event.transcript.results:
            if result.is_partial:
                continue
            for alt in result.alternatives:
                if alt.transcript:
                    self._parts.append(alt.transcript)

    @property
    def transcript(self) -> str:
        return " ".join(self._parts)


class TranscribeStt:
    """AWS Transcribe 스트리밍 STT(짧은 클립). 실제 스트리밍 호출은 인프라에서 검증."""

    def __init__(
        self,
        *,
        language: str = "ko-KR",
        region: str = "ap-northeast-2",
        sample_rate_hz: int = 16000,
        media_encoding: str = "pcm",
    ) -> None:
        self._language = language
        self._region = region
        self._sample_rate = sample_rate_hz
        self._media_encoding = media_encoding

    async def transcribe(self, audio: bytes, *, content_type: str) -> str:  # pragma: no cover - infra
        client = TranscribeStreamingClient(region=self._region)
        stream = await client.start_stream_transcription(
            language_code=self._language,
            media_sample_rate_hz=self._sample_rate,
            media_encoding=self._media_encoding,
        )
        collector = _TranscriptCollector(stream.output_stream)

        async def _write_chunks() -> None:
            for i in range(0, len(audio), _AUDIO_CHUNK):
                await stream.input_stream.send_audio_event(audio_chunk=audio[i : i + _AUDIO_CHUNK])
            await stream.input_stream.end_stream()

        await asyncio.gather(_write_chunks(), collector.handle_events())
        return collector.transcript
