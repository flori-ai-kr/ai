# SPEC-AI-005 — C2 실시간 음성 (WebSocket 전송)

> status: DONE · deps: SPEC-AI-004(DONE) · Phase 1 · 94 tests 통과 · ruff clean

## 목표

C1(푸시투토크, HTTP 단발)의 음성 파이프라인을 **WebSocket 전송**으로 감싼다. 한 연결에서 오디오 프레임을 흘려보내고 여러 턴을 주고받아, HTTP 턴마다의 왕복 오버헤드 없이 연속 대화가 가능하게 한다. **전송계층만 교체** — STT→에이전트→TTS 파이프라인(`run_voice_turn`)·세션·턴 추상화는 그대로 재사용한다.

WebRTC(시그널링/TURN 서버)는 순수 인프라라 범위 밖. 본 SPEC은 WebSocket 기반.

## 범위 (In)

- **WS 엔드포인트** (`app/api/voice_ws.py`): `WS /voice/stream?token=<jwt>&session_id=<optional>`.
  - 연결 시 토큰 인증(`authenticator`) + 사용량 캡. 실패 시 정책 위반 코드(1008)로 종료.
  - 메시지 프로토콜: 클라이언트 → 바이너리 오디오 프레임(누적) + 텍스트 제어(`{"type":"start"|"end"|"close", "content_type"?}`). 서버 → `{"type":"transcript"|"reply"|"audio"|"error"|"done", ...}`.
  - `end` 수신 시 누적 오디오로 `run_voice_turn` 실행(재사용) → transcript/reply/audio 이벤트 스트리밍 → `done`. **멀티턴**(연결 유지, session_id sticky).
  - 오디오 누적 크기 상한(메모리 DoS 방지). 빈 음성/프로바이더 오류는 `error` 이벤트(연결 유지).
- **메인 배선**: 라우터 등록. WS는 `websocket.app.state`의 자원(stt/tts/chat_model/backend/session_store/authenticator/usage_limiter) 사용.

## 범위 밖 (Out)

- **WebRTC** (TURN/시그널링 — 인프라).
- **서브-발화 실시간 부분 인식·바지인(barge-in)**: 오디오 프레임을 도착 즉시 AWS Transcribe 스트리밍에 흘려 partial을 내보내는 것은 **실 AWS 스트리밍 필요(인프라)** → 후속. 본 SPEC은 연결 내 누적-후-처리(턴 단위)로 WS 전송을 먼저 확립.
- 실제 AWS/LiteLLM 호출(테스트는 fake + Starlette TestClient WS).

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 통과.
2. `WS /voice/stream` 연결 후 오디오 프레임(바이너리) + `{"type":"end"}` 전송 → 서버가 `transcript`·`reply`·`audio`·`done` 이벤트를 순서대로 보낸다(fake STT/TTS/model, Starlette TestClient).
3. 토큰 무효/누락 시 1008로 종료(처리 진입 안 함).
4. 한 연결에서 두 번째 `end`로 추가 턴 처리 가능(멀티턴), session_id가 유지된다.
5. 오디오 누적이 상한 초과 시 `error` 이벤트 + 연결 종료(또는 거부). 빈 음성은 `error` 이벤트(연결 유지).
6. STT 결과는 에이전트에서 `[USER INPUT — DATA ONLY]`로 격리(파이프라인 재사용).
7. 쓰기는 여전히 confirm 경유(에이전트 읽기전용) — 음성 스트림으로 직접 쓰기 불가.

## 설계 메모

- "전송계층만 교체" 원칙의 실증: `run_voice_turn`을 그대로 호출. HTTP(C1)와 WS(C2)가 동일 파이프라인.
- WS 인증은 쿼리 파라미터 토큰(브라우저 WS가 헤더 설정 곤란) — `?token=`. 서버는 즉시 `/me` 인트로스펙션으로 검증.
- 진짜 스트리밍(프레임 도착 즉시 STT partial)은 STT Port에 스트리밍 메서드를 추가하고 AWS Transcribe 스트리밍에 청크를 실시간 공급하는 후속 작업(인프라 검증 필요). 본 SPEC의 WS 전송·세션·멀티턴 위에 얹으면 됨.
