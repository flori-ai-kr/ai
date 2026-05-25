"""C1 음성 푸시투토크 — 녹음 오디오(base64) → STT → 에이전트 → TTS → 음성 응답(base64).

전송은 HTTP 단발. C2(실시간)에서 동일 파이프라인을 스트리밍 전송으로 감싼다.
"""

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.api.deps import (
    get_backend_client,
    get_chat_model,
    get_request_context,
    get_session_store,
    get_stt,
    get_tts,
)
from app.backend.auth import RequestContext
from app.backend.client import BackendClient
from app.session.store import SessionStore
from app.voice.pipeline import run_voice_turn
from app.voice.ports import SttProvider, TtsProvider

router = APIRouter()


class VoiceTurnRequest(BaseModel):
    audio_base64: str = Field(..., max_length=20_000_000)  # ~15MB raw
    content_type: str = Field("audio/wav", max_length=100)
    session_id: str | None = Field(None, max_length=64)


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

    return VoiceTurnResponse(
        transcript=result["transcript"],
        reply=result["reply"],
        audio_base64=base64.b64encode(result["audio_out"]).decode("ascii"),
        content_type=result["content_type"],
        session_id=result["session_id"],
    )
