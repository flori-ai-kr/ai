# SPEC-AI-004 — C1 음성 푸시투토크 (STT→에이전트→TTS)

> status: DONE · deps: SPEC-AI-001(DONE), SPEC-AI-003(DONE) · Phase 1 · 77 tests 통과 · ruff clean

## 목표

음성 지시("내일 2시 김미영님 장미다발 예약 잡아줘")를 **푸시투토크(녹음 후 전송, HTTP)** 로 받아 STT로 텍스트화하고, A에서 만든 ReAct 에이전트를 태운 뒤 응답을 TTS로 음성화해 돌려준다. 전송계층 독립(세션·턴 추상화) 위에 올려 C2(실시간 WS/WebRTC)에서 전송만 교체 가능하게 한다. STT/TTS = **AWS Transcribe/Polly**, Port로 추상화.

## 범위 (In)

- **STT/TTS Port** (`app/voice/ports.py`): `SttProvider`(`transcribe(audio, *, content_type) -> str`), `TtsProvider`(`synthesize(text) -> (audio_bytes, content_type)`) Protocol. 프로바이더 중립.
- **음성 턴 파이프라인** (`app/voice/pipeline.py`): `run_voice_turn(stt, tts, model, client, ctx, audio, content_type, session_store, session_id) -> {transcript, reply, audio_out, content_type, session_id}` — STT → `run_agent`(A 재사용) → TTS. 세션 턴 기록(유저=transcript, 어시스턴트=reply).
- **엔드포인트** (`app/api/voice.py`): `POST /voice/turn` {audio_base64, content_type, session_id?} → 디코드 → 파이프라인 → {transcript, reply, audio_base64, content_type, session_id}. 인증·캡 동일 적용.
- **AWS 어댑터** (`app/voice/aws.py`): `PollyTts`(boto3 polly `synthesize_speech`, `to_thread`), `TranscribeStt`(amazon-transcribe 스트리밍, 짧은 클립 transcript 수집). env: region, Polly voice(기본 Seoyeon), 언어(ko-KR).
- **배선**: config에 음성 설정, lifespan에서 app.state.stt/tts 구성.

## 범위 밖 (Out)

- C2 실시간(WS/WebRTC, → SPEC-AI-005). 선제 제안(→ D).
- 실제 AWS Transcribe/Polly 호출(테스트는 fake Port + boto3 mock). 실 자격/스트리밍 검증은 인프라(범위 밖).
- 오디오 포맷 변환·노이즈 처리. 클라이언트가 지원 포맷(PCM/mp3 등)으로 전송 전제.

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 통과.
2. `run_voice_turn`: fake STT가 transcript를 주고 fake model이 응답을 주면, TTS audio_out과 reply/transcript를 반환하고 세션에 유저·어시스턴트 턴이 기록된다.
3. `POST /voice/turn`: 미인증 401. 유효 시 200 + `{transcript, reply, audio_base64, content_type, session_id}`. audio_base64는 디코딩 가능한 base64.
4. 음성 입력(STT 결과 텍스트)이 에이전트에서 `[USER INPUT — DATA ONLY]`로 격리된다(A 경로 재사용).
5. `PollyTts`가 boto3 polly `synthesize_speech`를 올바른 파라미터(text/voice/format)로 호출하고 audio 바이트를 반환한다(boto3 mock).
6. `TranscribeStt`의 transcript 수집기가 partial은 무시하고 final 결과만 누적한다(스트림 이벤트 단위 단위테스트).
7. 음성 경로의 쓰기(예약 생성 등)도 여전히 human-in-loop — 에이전트 루프는 읽기전용(is_write 차단). (음성으로 예약은 D/후속에서 확인 카드 음성화와 함께)

## 설계 메모

- 음성은 **A의 ReAct 루프를 그대로 재사용** — STT가 앞단, TTS가 뒷단. 채널 무관 세션·턴 추상화 덕에 텍스트/음성이 동일 그래프.
- STT/TTS는 Port 주입 — 테스트는 fake, prod는 AWS. C에서 엔진 교체는 어댑터만.
- 푸시투토크(HTTP 단발)이므로 동기 요청/응답. C2에서 동일 파이프라인을 스트리밍 전송으로 감싼다.
- 음성 응답은 텍스트 reply의 TTS — 길면 잘릴 수 있어 후속에서 분할/요약 고려(백로그).
