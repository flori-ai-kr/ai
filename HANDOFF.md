# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-05-25)

**Phase 1 — SPEC-AI-001(Foundation) 구현 완료. PR(→ dev) 진행.**

### 완료
- DESIGN 승인됨(2026-05-25). README는 영어로 전환(공개 레포 정책).
- 부트스트랩: MoAI 초기화, 컨벤션 문서, GitHub `flori-ai-kr/ai`(public, dev 디폴트), 라벨·About·CI.
- **SPEC-AI-001 구현** (`feature/SPEC-AI-001`): uv 프로젝트(py3.12)·ruff·pytest, FastAPI 앱(`/health`, 보호 `/whoami`), 인증 의존성(`/me` 인트로스펙션+패스스루), 백엔드 클라이언트(httpx, JWT 패스스루, 재시도/에러매핑), Redis 세션(session_id+턴), 사용량 캡, 감사 로깅(PII 마스킹), LiteLLM ChatOpenAI 팩토리, LangGraph 스켈레톤, docker-compose+Dockerfile+.env.example+litellm-config.
- 검증: `ruff check` clean · `ruff format --check` clean · **pytest 28 passed** · `docker compose config` 유효.

### 다음 할 일
1. `feature/SPEC-AI-001` → **dev PR** (`/feature-finalize`). CI 통과 확인 후 머지.
2. 머지 후 → SPEC-AI-002(A 데이터 분석, 읽기전용 도구콜 루프) 착수.

### 블로커
- 없음.

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트(JWT `Authorization: Bearer`, `TenantContext` userId 격리). 도구 카탈로그는 DESIGN §6.
- 시크릿(LiteLLM master key, Bedrock 자격)은 env로만. 인프라/배포는 범위 밖.
- CI는 첫 PR부터 정식 동작(pyproject.toml 존재 → graceful skip 해제). `commit-labeler`는 레포 시크릿 `PERSONAL_TOKEN` 필요.
- §14 열린 질문(캡 정책/세션 식별/ConfirmationCard 계약 등)은 기능 SPEC에서 구체화 — 현재 합리적 기본값으로 seam 구현.
