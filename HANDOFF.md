# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-05-25)

**Phase 1 — SPEC-AI-001 머지 완료. SPEC-AI-002(A 데이터 분석) 구현 완료, PR(→ dev) 진행.**

### 완료
- DESIGN 승인. 부트스트랩 + GitHub `flori-ai-kr/ai`(public, dev 디폴트, 라벨·About·CI). README 영어.
- **SPEC-AI-001(Foundation)** — dev 머지 완료(PR #1). FastAPI 앱, 인증(`/me` 패스스루), 백엔드 클라이언트, Redis 세션, 사용량 캡, 감사 로깅, LiteLLM 팩토리, LangGraph 스켈레톤, 로컬 스택. CI 그린. (신규 org Actions 최초 등록 지연 → 새 이벤트로 정상화됨)
- **SPEC-AI-002(A 데이터 분석)** (`feature/SPEC-AI-002`): 읽기 도구 레지스트리(`get_month_dashboard`/`get_today_dashboard`/`list_sales`/`list_customers`, JWT 패스스루), ReAct 도구콜 루프(iteration cap·self-correction·감사 로깅), 분석가 시스템 프롬프트(입력 펜스), `POST /chat`(인증+세션+에이전트). 전부 읽기전용.
- 검증: `ruff check` clean · `ruff format --check` clean · **pytest 41 passed**.

### 다음 할 일
1. `feature/SPEC-AI-002` → **dev PR**(`/feature-finalize`) → CI 그린 → 머지.
2. 머지 후 → SPEC-AI-003(B OCR→예약, 비전 + human-in-loop 쓰기) 착수.

### 블로커
- 없음.

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트(JWT `Authorization: Bearer`, `TenantContext` userId 격리). 도구 카탈로그는 DESIGN §6.
- 시크릿(LiteLLM master key, Bedrock 자격)은 env로만. 인프라/배포는 범위 밖.
- CI는 첫 PR부터 정식 동작(pyproject.toml 존재 → graceful skip 해제). `commit-labeler`는 레포 시크릿 `PERSONAL_TOKEN` 필요.
- §14 열린 질문(캡 정책/세션 식별/ConfirmationCard 계약 등)은 기능 SPEC에서 구체화 — 현재 합리적 기본값으로 seam 구현.
