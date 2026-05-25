import io

from amazon_transcribe.model import Alternative, Result, Transcript, TranscriptEvent

from app.voice.aws import PollyTts, _TranscriptCollector


class _MockPollyClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def synthesize_speech(self, **kwargs):
        self.calls.append(kwargs)
        return {"AudioStream": io.BytesIO(b"mp3-bytes")}


async def test_polly_tts_synthesizes_with_voice_and_format():
    client = _MockPollyClient()
    tts = PollyTts(voice="Seoyeon", client=client)
    audio, content_type = await tts.synthesize("안녕하세요 사장님")

    assert audio == b"mp3-bytes"
    assert content_type == "audio/mpeg"
    call = client.calls[0]
    assert call["Text"] == "안녕하세요 사장님"
    assert call["VoiceId"] == "Seoyeon"
    assert call["OutputFormat"] == "mp3"


async def test_transcript_collector_keeps_only_final_results():
    collector = _TranscriptCollector(None)

    partial = TranscriptEvent(
        transcript=Transcript(
            results=[
                Result(
                    result_id="r1",
                    start_time=0.0,
                    end_time=1.0,
                    is_partial=True,
                    alternatives=[Alternative(transcript="내일 두시", items=[], entities=None)],
                )
            ]
        )
    )
    final = TranscriptEvent(
        transcript=Transcript(
            results=[
                Result(
                    result_id="r1",
                    start_time=0.0,
                    end_time=2.0,
                    is_partial=False,
                    alternatives=[Alternative(transcript="내일 2시 예약", items=[], entities=None)],
                )
            ]
        )
    )

    await collector.handle_transcript_event(partial)
    await collector.handle_transcript_event(final)

    assert collector.transcript == "내일 2시 예약"
