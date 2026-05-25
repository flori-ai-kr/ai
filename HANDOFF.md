# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-05-25)

**Phase 1 — AI-001·AI-002 머지 완료. SPEC-AI-003(B OCR→예약) 구현 완료, PR(→ dev) 진행.**

### 완료
- DESIGN 승인. 부트스트랩 + GitHub `flori-ai-kr/ai`(public, dev 디폴트, 라벨·About·CI). README 영어.
- **AI-001(Foundation)** — 머지(PR #1). FastAPI, 인증(`/me` 패스스루), 백엔드 클라이언트, Redis 세션, 캡, 감사, LiteLLM, LangGraph 스켈레톤, 로컬 스택.
- **AI-002(A 데이터 분석)** — 머지(PR #2). 읽기 도구 레지스트리 + ReAct 루프 + `POST /chat`. 읽기전용.
- **AI-003(B OCR→예약)** (`feature/SPEC-AI-003`): 비전 추출(`extract_reservation_draft`, 멀티모달+JSON 파싱), `PendingWrite` 저장소(Redis, proposal_id·user_id·TTL·1회성), confirm executor(`POST /reservations`), `POST /ocr/reservation`(→ ConfirmationCard), `POST /confirm`(→ 실행). **첫 쓰기 경로** — human-in-loop. 에이전트 루프는 is_write 차단 유지.
- 검증: `ruff check` clean · `ruff format --check` clean · **pytest 65 passed**.

### 다음 할 일
1. `feature/SPEC-AI-003` → **dev PR**(`/feature-finalize`) → CI 그린 → 머지.
2. 머지 후 → SPEC-AI-004(C1 음성 푸시투토크: STT→에이전트→TTS, 전송 HTTP/SSE) 착수. STT/TTS 프로바이더 확정 필요(DESIGN §14-6).

### 블로커
- 없음.

### 백로그(후속 SPEC 권고)
- 에이전트: 세션 히스토리 길이 슬라이싱, 백엔드 응답 Pydantic 검증(LLM 출력 안전), REGISTRY name 키 중복 정리.
- 인증 캐시 멀티워커 시 Redis 이전, 백엔드 클라이언트 timeout 서브클래스.
- ConfirmationCard 필드 편집 후 수정 payload 확정 경로(앱 협의).

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트(JWT `Authorization: Bearer`, `TenantContext` userId 격리). 도구 카탈로그는 DESIGN §6.
- 시크릿(LiteLLM master key, Bedrock 자격)은 env로만. 인프라/배포는 범위 밖.
- CI는 첫 PR부터 정식 동작(pyproject.toml 존재 → graceful skip 해제). `commit-labeler`는 레포 시크릿 `PERSONAL_TOKEN` 필요.
- §14 열린 질문(캡 정책/세션 식별/ConfirmationCard 계약 등)은 기능 SPEC에서 구체화 — 현재 합리적 기본값으로 seam 구현.
