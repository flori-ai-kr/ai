# Flori AI — HANDOFF

> 직전 세션의 상태와 다음 할 일. 세션 시작 시 이 파일 + ROADMAP.md를 먼저 읽는다.

## 현재 상태 (2026-05-25)

**Phase 0 (설계) 진행 중 — 부트스트랩 완료, DESIGN 승인 대기.**

### 완료
- MoAI-ADK 초기화 (`moai init`, v2.14.0, mode=tdd, language=python). git 전략=personal, 통합 브랜치=dev.
- 컨벤션 문서: `CLAUDE.md`(hazel 컨벤션 + MoAI 통합), `ROADMAP.md`(AI-001~006 시퀀싱), 본 `HANDOFF.md`, `README.md`.
- MoAI 운영 매뉴얼 원본 백업: `CLAUDE.md.moai-template`.
- `docs/DESIGN.md` 초안 작성.
- GitHub: `flori-ai-kr/ai` (public) 생성, `main`/`dev` 브랜치, `dev` 디폴트. 라벨·About·README·CI(.github) 세팅.
- CI: `kikoai/app/.github` 복제(deploy-dev.yml 제외). `ci.yml`만 Python(uv+ruff+pytest)으로 조정.

### 다음 할 일
1. **사용자 DESIGN 승인 대기** — 승인 전 구현 착수 금지.
2. 승인 후 → SPEC-AI-001(Foundation) 착수: `.moai/specs/SPEC-AI-001/spec.md` 작성 → TDD → `uv run ruff check . && uv run pytest` 통과 → 커밋 → ROADMAP DONE.

### 블로커
- 없음.

### 메모
- 백엔드 REST 표면은 `~/Desktop/hazel-server`에 95개 엔드포인트 존재(JWT `Authorization: Bearer`, `TenantContext`로 userId 격리). 도구 카탈로그는 DESIGN §도구 카탈로그 참조.
- 시크릿(LiteLLM master key, Bedrock 자격 등)은 env로만. 인프라/배포는 범위 밖.
