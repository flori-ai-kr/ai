# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-06-04) — 게이트웨이 아키텍처 전환

**ai-server를 Spring 게이트웨이 뒤 stateless로 전환 + web 연동. 3레포(server·ai·web) dev 머지 완료.**

### 구조 (web ↔ ai 서로 모름)
- `web → Spring 게이트웨이 /ai/* → ai-server(내부망) → litellm → Bedrock`. web/모바일은 ai-server를 직접 호출하지 않는다.
- ai-server 무상태: `X-Internal-Key`(게이트웨이 신뢰) + `X-User-Id` + 유저 JWT(백엔드 도구 패스스루)로 호출받음. 대화 세션·메시지·쓰기 제안·proactive **로깅은 게이트웨이 DB(Postgres 4테이블)** 소유.

### ai-server 변경 (PR #7, dev 머지)
- 인증: `/me` 도입부 제거 → 게이트웨이 내부키 신뢰(`deps.get_request_context`, hmac 비교).
- `/chat`: 게이트웨이가 보낸 `messages` 히스토리 수신(세션 소유 제거), role Literal·길이 상한·last=user 검증.
- `/ocr/reservation`: 추출 draft만 반환(Redis pending·확인카드 제거). `/confirm` 제거(게이트웨이가 예약 생성). proactive 응답에 model 추가.
- 테스트 새 계약으로 갱신 — **84 passed**, ruff clean.

### 인프라 (dev)
- 모델: 품질 경로 **Sonnet 4.6**(litellm alias), 저지연 Haiku 4.5. IAM에 sonnet ARN 추가(aws-infra `variables.tf` 영구화).
- `https://litellm.flori.ai.kr`(ALB/TLS+UI), `https://langfuse.flori.ai.kr`(트레이싱 — litellm success_callback, 트레이스 흐름 확인). 키는 dev-ai `~/env/.env`.

### 다음 할 일
- dev 실로그인 E2E 클릭스루(`admin.flori.ai.kr` → 채팅/OCR/proactive). web repo 문서 갱신(다른 세션 작업 중이라 보류).

---

## (이전) 현재 상태 (2026-05-26)

**Phase 1 — 로드맵 6/6 SPEC 구현 완료. SPEC-AI-005(C2 WebSocket) 구현 완료, PR(→ dev) 진행. 나머지 5개 머지 완료.**

### 완료 (6/6 SPEC)
- **AI-005(C2 실시간 음성)** (`feature/SPEC-AI-005`): `WS /voice/stream`(WebSocket) — `run_voice_turn` 재사용, 멀티턴·session_id sticky, 토큰 인증·오디오 상한·event 프로토콜(`app/api/voice_ws.py`). WebRTC·실시간 partial/바지인은 인프라 후속.
- DESIGN 승인. 부트스트랩 + GitHub `flori-ai-kr/ai`(public, dev 디폴트, 라벨·About·CI). README 영어.
- **AI-001(Foundation)** — 머지(PR #1). FastAPI, 인증(`/me` 패스스루), 백엔드 클라이언트, Redis 세션, 캡, 감사, LiteLLM, LangGraph 스켈레톤, 로컬 스택.
- **AI-002(A 데이터 분석)** — 머지(PR #2). 읽기 도구 레지스트리 + ReAct 루프 + `POST /chat`.
- **AI-003(B OCR→예약)** — 머지(PR #3). 비전 추출 → ConfirmationCard(human-in-loop) → `POST /confirm` → `POST /reservations`.
- **AI-004(C1 음성)** — 머지(PR #4). STT/TTS Port + AWS 어댑터(Transcribe/Polly) + `run_voice_turn` + `POST /voice/turn`.
- **AI-006(D 에이전트 확장)** (`feature/SPEC-AI-006`): 선제 제안 `GET /agent/proactive`(읽기 컨텍스트→LLM 제안, fail-open) + 관측성 seam(`app/observability/tracing.py` `@observe` no-op, run_agent/proactive 적용).
- 검증: `ruff` clean · `format` clean · **pytest 94 passed**.

### 다음 할 일
1. `feature/SPEC-AI-005` → **dev PR**(`/feature-finalize`) → CI 그린 → 머지. (머지되면 **로드맵 6/6 완료**)
2. 이후 남은 것은 전부 선택 사항: 인프라 연동(사용자 담당), 아래 백로그, `flori-ai/mobile` 앱 연동.

### 블로커
- 없음.

### 백로그 (선택 — 후속 개선)
- 실시간 음성 심화: 오디오 프레임 도착 즉시 AWS Transcribe 스트리밍 공급 → partial/바지인. WebRTC(TURN/시그널링) 전송.
- 인-챗 예약 제안 도구(propose_reservation)를 ReAct 루프에 통합(현재 B는 /ocr+/confirm).
- 세션 동시쓰기 store-레벨 원자화, 인증 캐시 Redis 이전(멀티워커), 감사 durable 저장, 백엔드 응답 Pydantic 검증, 세션 히스토리 슬라이싱, REGISTRY name 키 중복 정리, ConfirmationCard 필드 편집 confirm 경로.
- 인프라 연동(사용자): 실 LiteLLM→Bedrock, AWS Transcribe/Polly 자격, Langfuse, 배포.

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트(JWT `Authorization: Bearer`, `TenantContext` userId 격리). 도구 카탈로그는 DESIGN §6.
- 시크릿(LiteLLM master key, Bedrock 자격)은 env로만. 인프라/배포는 범위 밖.
- CI는 첫 PR부터 정식 동작(pyproject.toml 존재 → graceful skip 해제). `commit-labeler`는 레포 시크릿 `PERSONAL_TOKEN` 필요.
- §14 열린 질문(캡 정책/세션 식별/ConfirmationCard 계약 등)은 기능 SPEC에서 구체화 — 현재 합리적 기본값으로 seam 구현.
