# Flori AI — ROADMAP

자율 실행의 단일 진입점. 세션은 이 파일을 먼저 읽고, `status: TODO`이며 `deps`가 모두 `DONE`인 첫 SPEC을 골라 진행한다.
완료 시 해당 SPEC의 status를 `DONE`으로 바꾸고 `HANDOFF.md`를 갱신한다.

상태값: `TODO` | `DOING` | `DONE` | `BLOCKED`

## Phase 0 — 설계

| 항목 | status | 비고 |
|------|--------|------|
| docs/DESIGN.md | DOING | 전체 아키텍처·보안 모델·도구 카탈로그·대화 세션·시퀀싱. **사용자 승인 게이트** — 승인 전 구현 착수 금지 |

## Phase 1 — 기반 & 기능 (시퀀싱)

> 가장 저렴·저위험인 A부터 도구콜 루프를 끝까지 검증한 뒤 B→C→D로 확장.

| SPEC | status | deps | 범위 |
|------|--------|------|------|
| SPEC-AI-001 | TODO | DESIGN 승인 | **Foundation**: FastAPI+LangGraph 스켈레톤, 유저 JWT 검증/전달 인증(`/me` 인트로스펙션 + 패스스루), 백엔드 REST 도구 클라이언트(httpx, 재시도/타임아웃), LiteLLM 연동(Claude Haiku 4.5), Redis 세션(session_id+턴 추상화), 로컬 docker-compose(ai-server+redis), `/health`, 유저별 사용량 캡 자리, AI 행위 감사 로깅, `.env.example`, pyproject(uv)·ruff·pytest |
| SPEC-AI-002 | TODO | 001 | **A 데이터 분석 (읽기전용)**: 통계/대시보드 읽기 도구(`/dashboard/month`, `/dashboard/today`, `/sales`, `/customers` 등 래퍼) + 도구콜 루프 + "이번 달 매출 왜 떨어졌어?" 류 질의에 LLM 해설. 쓰기 없음 — 도구콜 루프 검증의 기준점 |
| SPEC-AI-003 | TODO | 001, 002 | **B OCR→예약**: 이미지(카톡 스크린샷) 입력 → 비전 LLM(Haiku 4.5)로 고객·날짜·시간·품목·금액 추출 → 예약 후보 DTO → **확인 카드(human-in-loop)** → 확인 시 `find-or-create` 고객 + `POST /reservations`. 추출 검증·날짜 파싱·중복 방지 |
| SPEC-AI-004 | TODO | 001, 003 | **C1 음성 푸시투토크**: STT(확정 예정) → 텍스트 → 에이전트 도구 호출 → 응답 텍스트 → TTS. HTTP/SSE 전송. 대화 세션 추상화 위에서 동작. STT/TTS 프로바이더 추상화(교체 가능) |
| SPEC-AI-005 | TODO | 004 | **C2 실시간 음성**: WebSocket/WebRTC 전송으로 교체(전송계층만). 세션·턴 추상화 재사용. 부분 인식·바지인(barge-in) 고려 |
| SPEC-AI-006 | TODO | 002, 003, 004 | **D 에이전트 확장**: A·B·C 도구를 묶은 다단계 에이전트 + 선제 제안(예: "내일 예약 3건, 리마인더 보낼까요?"). Langfuse 트레이싱 도입 검토 |

## 진행 규칙
- 한 세션은 SPEC을 **하나씩** 끝낸다(lint·테스트·커밋까지). 그 후 다음 TODO로.
- 의존성 미충족 SPEC은 건너뛰지 않고, 충족된 가장 앞 SPEC을 택한다.
- 모든 SPEC은 `.moai/specs/<SPEC-ID>/spec.md`에 인수기준을 먼저 적고 구현한다.
- **DESIGN 승인 전에는 어떤 구현 SPEC도 착수하지 않는다.**

## 결정 보류 (DESIGN에서 확정 / 추후)
- STT/TTS 프로바이더: AWS Transcribe/Polly vs Naver Clova vs OpenAI — C(AI-004) 단계에서 한국어·꽃 도메인 기준 확정.
- Langfuse 트레이싱 도입 시점: D(AI-006) 또는 에이전트 복잡도 상승 시.
- 사용량 캡·감사 로그의 durable 저장: v1은 Redis + 구조화 로그. 영속 필요 시 백엔드 내부 엔드포인트 추가 검토.
