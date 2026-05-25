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

import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.backend.auth import AuthError
from app.core.usage import UsageCapExceeded
from app.voice.pipeline import EmptyTranscriptError, run_voice_turn
from app.voice.ports import VoiceProviderError

router = APIRouter()

_WS_POLICY_VIOLATION = 1008
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 누적 상한 (메모리 DoS 방지)


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
    content_type = "audio/wav"
    buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()
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
                content_type = event.get("content_type", content_type)
                buffer.clear()
            elif etype == "close":
                break
            elif etype == "end":
                if not buffer:
                    await websocket.send_json({"type": "error", "detail": "no audio received"})
                    continue
                try:
                    result = await run_voice_turn(
                        stt=state.stt,
                        tts=state.tts,
                        model=state.chat_model,
                        client=state.backend,
                        ctx=ctx,
                        audio=bytes(buffer),
                        content_type=content_type,
                        store=state.session_store,
                        session_id=session_id,
                    )
                except EmptyTranscriptError:
                    await websocket.send_json({"type": "error", "detail": "no speech recognized"})
                    buffer.clear()
                    continue
                except PermissionError:
                    await websocket.send_json({"type": "error", "detail": "session access denied"})
                    await websocket.close(code=_WS_POLICY_VIOLATION)
                    return
                except VoiceProviderError:
                    await websocket.send_json({"type": "error", "detail": "voice provider error"})
                    buffer.clear()
                    continue

                session_id = result["session_id"]  # sticky — 다음 턴에 재사용
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
