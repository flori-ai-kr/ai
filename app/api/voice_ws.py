"""C2 실시간 음성 — WebSocket 전송.

C1의 음성 파이프라인(`run_voice_turn`)을 그대로 재사용하되 전송계층만 WebSocket으로 교체한다.
한 연결에서 오디오 프레임을 흘려보내고 여러 턴을 주고받는다(멀티턴, session_id sticky).

프로토콜
- client → 바이너리 오디오 프레임(누적) + 텍스트 제어: {"type":"start"|"end"|"close", "content_type"?}
- server → {"type":"transcript"|"reply"|"audio"|"error"|"done", ...}

인증은 쿼리 파라미터 토큰(?token=) — 브라우저 WS가 헤더 설정이 어려워 표준 관행.
진짜 서브-발화 스트리밍(부분 인식/바지인)은 AWS Transcribe 스트리밍에 청크를 실시간 공급하는
후속 작업(인프라 검증 필요). 본 핸들러는 WS 전송·세션·멀티턴을 먼저 확립한다.
"""

import asyncio
import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.validators import is_safe_id
from app.backend.auth import AuthError
from app.core.audit import audit_event
from app.core.usage import UsageCapExceeded
from app.voice.pipeline import EmptyTranscriptError, run_voice_turn
from app.voice.ports import VoiceProviderError

router = APIRouter()

_WS_POLICY_VIOLATION = 1008
_WS_INTERNAL_ERROR = 1011
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 누적 상한 (메모리 DoS 방지)
_IDLE_TIMEOUT_S = 60.0  # 유휴 연결 점유 방지
_TURN_TIMEOUT_S = 60.0  # 한 턴 처리 상한
# C1(voice.py)과 동일한 허용 포맷 — Transcribe 스트리밍 호환.
_ALLOWED_CONTENT_TYPES = frozenset({"audio/wav", "audio/pcm", "audio/ogg", "audio/x-wav"})


@router.websocket("/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    state = websocket.app.state

    token = websocket.query_params.get("token", "")
    try:
        ctx = await state.authenticator.authenticate(token)
    except AuthError:
        await websocket.close(code=_WS_POLICY_VIOLATION)
        return
    try:
        await state.usage_limiter.enforce(ctx.user_id)
    except UsageCapExceeded:
        await websocket.close(code=_WS_POLICY_VIOLATION)
        return

    session_id: str | None = websocket.query_params.get("session_id") or None
    if session_id is not None and not is_safe_id(session_id):
        await websocket.close(code=_WS_POLICY_VIOLATION)  # Redis 키 오염 방지
        return
    content_type = "audio/wav"
    buffer = bytearray()

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=_IDLE_TIMEOUT_S)
            except TimeoutError:
                await websocket.close(code=1001)  # going away — 유휴 타임아웃
                return
            if message["type"] == "websocket.disconnect":
                break

            chunk = message.get("bytes")
            if chunk is not None:
                buffer.extend(chunk)
                if len(buffer) > _MAX_AUDIO_BYTES:
                    await websocket.send_json({"type": "error", "detail": "audio too large"})
                    await websocket.close(code=_WS_POLICY_VIOLATION)
                    return
                continue

            text = message.get("text")
            if text is None:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid control message"})
                continue

            etype = event.get("type")
            if etype == "start":
                new_ct = event.get("content_type", content_type)
                if new_ct not in _ALLOWED_CONTENT_TYPES:
                    await websocket.send_json({"type": "error", "detail": "unsupported content_type"})
                    continue
                content_type = new_ct
                buffer.clear()
            elif etype == "close":
                break
            elif etype == "end":
                if not buffer:
                    await websocket.send_json({"type": "error", "detail": "no audio received"})
                    continue
                try:
                    result = await asyncio.wait_for(
                        run_voice_turn(
                            stt=state.stt,
                            tts=state.tts,
                            model=state.chat_model,
                            client=state.backend,
                            ctx=ctx,
                            audio=bytes(buffer),
                            content_type=content_type,
                            store=state.session_store,
                            session_id=session_id,
                        ),
                        timeout=_TURN_TIMEOUT_S,
                    )
                except EmptyTranscriptError:
                    await websocket.send_json({"type": "error", "detail": "no speech recognized"})
                    buffer.clear()
                    continue
                except PermissionError:
                    audit_event("session_access_denied", user_id=ctx.user_id, session_id=session_id)
                    await websocket.send_json({"type": "error", "detail": "session access denied"})
                    await websocket.close(code=_WS_POLICY_VIOLATION)
                    return
                except (VoiceProviderError, TimeoutError):
                    audit_event("voice_provider_error", user_id=ctx.user_id, session_id=session_id)
                    await websocket.send_json({"type": "error", "detail": "voice processing failed"})
                    buffer.clear()
                    continue
                except Exception:
                    audit_event("voice_ws_unexpected_error", user_id=ctx.user_id, session_id=session_id)
                    await websocket.send_json({"type": "error", "detail": "internal error"})
                    await websocket.close(code=_WS_INTERNAL_ERROR)
                    return

                session_id = result["session_id"]  # sticky — 다음 턴에 재사용
                audit_event("voice_turn", user_id=ctx.user_id, session_id=session_id)
                await websocket.send_json({"type": "transcript", "text": result["transcript"]})
                await websocket.send_json({"type": "reply", "text": result["reply"], "session_id": session_id})
                await websocket.send_json(
                    {
                        "type": "audio",
                        "content_type": result["content_type"],
                        "audio_base64": base64.b64encode(result["audio_out"]).decode("ascii"),
                    }
                )
                await websocket.send_json({"type": "done"})
                buffer.clear()
    except WebSocketDisconnect:
        pass
