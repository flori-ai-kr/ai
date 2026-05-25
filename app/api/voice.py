"""C1 음성 푸시투토크 — 녹음 오디오(base64) → STT → 에이전트 → TTS → 음성 응답(base64).

전송은 HTTP 단발. C2(실시간)에서 동일 파이프라인을 스트리밍 전송으로 감싼다.
"""

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, field_validator

from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_session_store,
    get_stt,
    get_tts,
)
from app.api.validators import SafeId
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.core.audit import audit_event
from app.session.store import SessionStore
from app.voice.pipeline import EmptyTranscriptError, run_voice_turn
from app.voice.ports import SttProvider, TtsProvider, VoiceProviderError

router = APIRouter()

_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 디코딩 후 상한 (메모리/비용 DoS 방지)
# Transcribe 스트리밍 호환 포맷만 허용.
_ALLOWED_CONTENT_TYPES = frozenset({"audio/wav", "audio/pcm", "audio/ogg", "audio/x-wav"})


class VoiceTurnRequest(BaseModel):
    audio_base64: str = Field(..., max_length=20_000_000)  # ~15MB base64
    content_type: str = Field("audio/wav", max_length=64)
    session_id: SafeId | None = None

    @field_validator("content_type")
    @classmethod
    def _check_content_type(cls, v: str) -> str:
        if v not in _ALLOWED_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {sorted(_ALLOWED_CONTENT_TYPES)}")
        return v


class VoiceTurnResponse(BaseModel):
    transcript: str
    reply: str
    audio_base64: str
    content_type: str
    session_id: str


@router.post("/voice/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    req: VoiceTurnRequest,
    ctx: RequestContext = Depends(get_request_context),
    stt: SttProvider = Depends(get_stt),
    tts: TtsProvider = Depends(get_tts),
    model: BaseChatModel = Depends(get_chat_model),
    backend: BackendClient = Depends(get_backend_client),
    store: SessionStore = Depends(get_session_store),
) -> VoiceTurnResponse:
    try:
        audio = base64.b64decode(req.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="audio_base64 must be valid base64") from None

    if len(audio) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="audio payload too large")

    try:
        result: dict[str, Any] = await run_voice_turn(
            stt=stt,
            tts=tts,
            model=model,
            client=backend,
            ctx=ctx,
            audio=audio,
            content_type=req.content_type,
            store=store,
            session_id=req.session_id,
        )
    except EmptyTranscriptError:
        raise HTTPException(status_code=422, detail="음성을 인식하지 못했어요. 다시 시도해 주세요.") from None
    except PermissionError:
        audit_event("session_access_denied", user_id=ctx.user_id, session_id=req.session_id)
        raise HTTPException(status_code=403, detail="session access denied") from None
    except VoiceProviderError:
        audit_event("voice_provider_error", user_id=ctx.user_id, session_id=req.session_id)
        raise HTTPException(status_code=502, detail="음성 처리 중 오류가 발생했어요.") from None

    # transcript 본문은 로깅하지 않음(PII) — 사실만 기록.
    audit_event("voice_turn", user_id=ctx.user_id, session_id=result["session_id"])
    return VoiceTurnResponse(
        transcript=result["transcript"],
        reply=result["reply"],
        audio_base64=base64.b64encode(result["audio_out"]).decode("ascii"),
        content_type=result["content_type"],
        session_id=result["session_id"],
    )
