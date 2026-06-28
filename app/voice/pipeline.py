"""음성 턴 파이프라인 (C1 푸시투토크): STT → ReAct 에이전트(A 재사용) → TTS.

전송계층 독립 — 같은 세션·턴 추상화 위에서 텍스트/음성이 동일 그래프를 탄다.
C2(실시간)에서는 이 파이프라인을 스트리밍 전송으로 감싸기만 한다.
"""

import uuid
from typing import Any

from app.agents.react_loop import run_agent
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.observability.tracing import observe
from app.session.models import Turn
from app.session.store import SessionStore
from app.voice.ports import SttProvider, TtsProvider

_MAX_TRANSCRIPT_CHARS = 2000  # 음성 1턴 현실적 상한 (비용/컨텍스트 보호)
_MAX_TTS_CHARS = 2800  # Polly neural 입력 한도(~3000자) 안전 여유


class EmptyTranscriptError(Exception):
    """STT가 빈 결과를 반환(묵음/인식 실패)."""


@observe(name="run_voice_turn")
async def run_voice_turn(
    *,
    stt: SttProvider,
    tts: TtsProvider,
    model: Any,
    client: BackendClient,
    ctx: RequestContext,
    audio: bytes,
    content_type: str,
    store: SessionStore,
    session_id: str | None = None,
) -> dict[str, Any]:
    transcript = await stt.transcribe(audio, content_type=content_type)
    if not transcript.strip():
        raise EmptyTranscriptError("no speech recognized")
    transcript = transcript[:_MAX_TRANSCRIPT_CHARS]

    session_id = session_id or uuid.uuid4().hex
    session = await store.get_or_create(session_id, ctx.user_id)
    history = list(session.turns)
    await store.append_turn(session_id, Turn(role="user", text=transcript, kind="audio"), user_id=ctx.user_id)

    reply = await run_agent(model=model, client=client, ctx=ctx, user_text=transcript, history=history)

    await store.append_turn(session_id, Turn(role="assistant", text=reply, kind="audio"), user_id=ctx.user_id)
    audio_out, out_content_type = await tts.synthesize(reply[:_MAX_TTS_CHARS])

    return {
        "transcript": transcript,
        "reply": reply,
        "audio_out": audio_out,
        "content_type": out_content_type,
        "session_id": session_id,
    }
