# Flori AI — ROADMAP

자율 실행의 단일 진입점. 세션은 이 파일을 먼저 읽고, `status: TODO`이며 `deps`가 모두 `DONE`인 첫 SPEC을 골라 진행한다.
완료 시 해당 SPEC의 status를 `DONE`으로 바꾸고 `HANDOFF.md`를 갱신한다.

상태값: `TODO` | `DOING` | `DONE` | `BLOCKED`

## Phase 0 — 설계

| 항목 | status | 비고 |
|------|--------|------|
| docs/DESIGN.md | DONE | 전체 아키텍처·보안 모델·도구 카탈로그·대화 세션·시퀀싱. **사용자 승인 완료(2026-05-25)** |

## Phase 1 — 기반 & 기능 (시퀀싱)

> 가장 저렴·저위험인 A부터 도구콜 루프를 끝까지 검증한 뒤 B→C→D로 확장.

| SPEC | status | deps | 범위 |
|------|--------|------|------|
| SPEC-AI-001 | DONE | DESIGN 승인 | **Foundation**: FastAPI+LangGraph 스켈레톤, 유저 JWT 검증/전달 인증(`/me` 인트로스펙션 + 패스스루), 백엔드 REST 도구 클라이언트(httpx, 재시도/타임아웃), LiteLLM 연동(Claude Haiku 4.5), Redis 세션(session_id+턴 추상화), 로컬 docker-compose(ai-server+redis), `/health`, 유저별 사용량 캡 자리, AI 행위 감사 로깅, `.env.example`, pyproject(uv)·ruff·pytest. **28 tests 통과** |
| SPEC-AI-002 | DONE | 001 | **A 데이터 분석 (읽기전용)**: 통계/대시보드 읽기 도구(`/dashboard/month`, `/dashboard/today`, `/sales`, `/customers` 래퍼) + ReAct 도구콜 루프 + `POST /chat`로 "이번 달 매출 왜 떨어졌어?" 류 LLM 해설. 쓰기 없음. **41 tests 통과** |
| SPEC-AI-003 | DONE | 001, 002 | **B OCR→예약**: 이미지 → 비전 LLM(Haiku 4.5) 추출 → 예약 후보 → **확인 카드(human-in-loop)** `POST /ocr/reservation` → 확인 `POST /confirm` 시 `POST /reservations`. 쓰기는 confirm 경유만(에이전트 루프는 is_write 차단). proposal: user_id 바인딩·TTL·1회성. **65 tests 통과** |
| SPEC-AI-004 | DONE | 001, 003 | **C1 음성 푸시투토크**: `POST /voice/turn`(audio base64) → STT(AWS Transcribe) → ReAct 에이전트(A 재사용) → TTS(AWS Polly) → 음성 응답. STT/TTS Port 추상화(교체 가능). 전송 HTTP. **77 tests 통과** |
| SPEC-AI-005 | DONE | 004 | **C2 실시간 음성**: `WS /voice/stream`(WebSocket 전송) — `run_voice_turn` 재사용, 멀티턴·session_id sticky, 토큰 인증·오디오 누적 상한. WebRTC 및 서브-발화 실시간 partial/바지인은 인프라 필요 → 후속. **94 tests 통과** |
| SPEC-AI-006 | DONE | 002, 003, 004 | **D 에이전트 확장**: 선제 제안 `GET /agent/proactive`(읽기 컨텍스트 → LLM 제안, fail-open) + Langfuse 관측성 seam(`@observe` no-op 폴백, `run_agent`/proactive 적용). 제안→실행은 confirm 경유 유지. **90 tests 통과** |

## 진행 규칙
- 한 세션은 SPEC을 **하나씩** 끝낸다(lint·테스트·커밋까지). 그 후 다음 TODO로.
- 의존성 미충족 SPEC은 건너뛰지 않고, 충족된 가장 앞 SPEC을 택한다.
- 모든 SPEC은 `docs/specs/<SPEC-ID>.md`에 인수기준을 먼저 적고 구현한다.
- **DESIGN 승인 전에는 어떤 구현 SPEC도 착수하지 않는다.**

## 결정 보류 (DESIGN에서 확정 / 추후)
- STT/TTS 프로바이더: AWS Transcribe/Polly vs Naver Clova vs OpenAI — C(AI-004) 단계에서 한국어·꽃 도메인 기준 확정.
- Langfuse 트레이싱 도입 시점: D(AI-006) 또는 에이전트 복잡도 상승 시.
- 사용량 캡·감사 로그의 durable 저장: v1은 Redis + 구조화 로그. 영속 필요 시 백엔드 내부 엔드포인트 추가 검토.
