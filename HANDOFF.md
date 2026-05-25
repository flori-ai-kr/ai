# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-05-25)

**Phase 1 — AI-001·002·003·004 머지 완료. SPEC-AI-006(D 에이전트 확장) 구현 완료, PR(→ dev) 진행.**

### 완료 (5/6 SPEC 머지, AI-005만 보류)
- DESIGN 승인. 부트스트랩 + GitHub `flori-ai-kr/ai`(public, dev 디폴트, 라벨·About·CI). README 영어.
- **AI-001(Foundation)** — 머지(PR #1). FastAPI, 인증(`/me` 패스스루), 백엔드 클라이언트, Redis 세션, 캡, 감사, LiteLLM, LangGraph 스켈레톤, 로컬 스택.
- **AI-002(A 데이터 분석)** — 머지(PR #2). 읽기 도구 레지스트리 + ReAct 루프 + `POST /chat`.
- **AI-003(B OCR→예약)** — 머지(PR #3). 비전 추출 → ConfirmationCard(human-in-loop) → `POST /confirm` → `POST /reservations`.
- **AI-004(C1 음성)** — 머지(PR #4). STT/TTS Port + AWS 어댑터(Transcribe/Polly) + `run_voice_turn` + `POST /voice/turn`.
- **AI-006(D 에이전트 확장)** (`feature/SPEC-AI-006`): 선제 제안 `GET /agent/proactive`(읽기 컨텍스트→LLM 제안, fail-open) + 관측성 seam(`app/observability/tracing.py` `@observe` no-op, run_agent/proactive 적용).
- 검증: `ruff` clean · `format` clean · **pytest 90 passed**.

### 다음 할 일
1. `feature/SPEC-AI-006` → **dev PR**(`/feature-finalize`) → CI 그린 → 머지.
2. 머지 후 남은 것: **SPEC-AI-005(C2 실시간 음성)** — 사용자 선택으로 보류. 재개 시 WS 전송으로 `run_voice_turn` 스트리밍 래핑(WebRTC/TURN은 인프라 범위 밖).

### 블로커
- 없음.

### 백로그
- 인-챗 예약 제안 도구(propose_reservation)를 ReAct 루프에 통합(현재 B는 /ocr+/confirm).
- 세션 동시쓰기 store-레벨 원자화, 인증 캐시 Redis 이전, 감사 durable 저장, 백엔드 응답 Pydantic 검증.
- 실 Langfuse 연동(env), 실 AWS Transcribe/Polly 인프라 검증.

### 백로그(후속 SPEC 권고)
- 에이전트: 세션 히스토리 길이 슬라이싱, 백엔드 응답 Pydantic 검증(LLM 출력 안전), REGISTRY name 키 중복 정리.
- 인증 캐시 멀티워커 시 Redis 이전, 백엔드 클라이언트 timeout 서브클래스.
- ConfirmationCard 필드 편집 후 수정 payload 확정 경로(앱 협의).

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트(JWT `Authorization: Bearer`, `TenantContext` userId 격리). 도구 카탈로그는 DESIGN §6.
- 시크릿(LiteLLM master key, Bedrock 자격)은 env로만. 인프라/배포는 범위 밖.
- CI는 첫 PR부터 정식 동작(pyproject.toml 존재 → graceful skip 해제). `commit-labeler`는 레포 시크릿 `PERSONAL_TOKEN` 필요.
- §14 열린 질문(캡 정책/세션 식별/ConfirmationCard 계약 등)은 기능 SPEC에서 구체화 — 현재 합리적 기본값으로 seam 구현.
