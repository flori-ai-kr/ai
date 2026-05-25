# Flori AI — 꽃집 SaaS 프리미엄 AI 서비스

Flori(꽃집 SaaS)의 프리미엄 AI 기능을 담당하는 **별도 AI 서비스**. FastAPI + LangGraph.
자매 repo: `flori-ai/server`(Spring 백엔드 = `~/Desktop/hazel-server`), `flori-ai/mobile`(React Native 앱), `flori-ai/web`.

> MoAI-ADK 워크플로로 개발한다. MoAI 운영 매뉴얼 원본은 `CLAUDE.md.moai-template` 에 보존. 본 파일이 이 repo의 SSOT 지침이다.

## 이 repo의 역할

꽃집 사장(1인 운영, 손이 바쁨)을 위한 AI 기능을 제공한다. **백엔드 DB에 직접 접근하지 않고**, 기존 Spring REST API(`hazel-server`)를 도구로 호출하는 얇은 AI 오케스트레이션 레이어다.

- **A 데이터 분석**: "이번 달 매출 왜 떨어졌어?" → 백엔드 통계 API를 도구로 읽어 LLM이 해설 (읽기전용)
- **B OCR→예약**: 카톡 대화 스크린샷 → 비전 LLM이 고객·날짜·시간·품목·금액 추출 → 예약 후보 → 사용자 확인 → 예약 생성
- **C 음성**: 음성 지시 → STT → 에이전트 도구 호출 → 음성 응답 (C1 푸시투토크 → C2 실시간)
- **D 에이전트**: A·B·C 도구를 묶어 다단계·선제 제안하는 에이전트로 확장

## 기술 스택

| 영역 | 선택 |
|------|------|
| 언어/패키지 | **Python 3.12+ / uv** |
| 프레임워크 | **FastAPI + uvicorn** |
| 에이전트 오케스트레이션 | **LangGraph** (StateGraph, ReAct 루프) |
| LLM/Vision | **LiteLLM 프록시 → AWS Bedrock Claude Haiku 4.5** (`bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0`, us-east-1 cross-region). 멀티모달 — B의 OCR도 동일 모델 |
| LLM 클라이언트 | OpenAI 호환 클라이언트로 LiteLLM 호출 (`langchain-openai` / `openai`) |
| 스키마 | **Pydantic v2** |
| HTTP | **httpx** (async) — 백엔드 REST 도구 클라이언트 |
| 세션/캐시 | **Redis** (대화 세션, 사용량 캡, pending 상태) |
| 트레이싱 | **Langfuse** (에이전트 복잡해지면 추가 — v1 선택) |
| 테스트/린트 | **pytest / ruff** |

## 아키텍처 원칙 (HARD)

- **멀티테넌시 = 보안 1순위** [HARD]: AI 서버는 클라이언트가 준 **유저 JWT를 그대로 백엔드 REST에 전달**한다. user_id 격리·구독 게이팅은 Spring이 강제한다. **AI에 god-mode DB 커넥션을 주지 않는다.**
- **도구(tool) = 백엔드 기존 REST 엔드포인트의 얇은 래퍼**: 에이전트의 행동공간 = 이미 검증된 API 표면. 새 행동이 필요하면 백엔드에 엔드포인트를 먼저 만든다(이 repo에서 우회 금지).
- **쓰기는 human-in-loop** [HARD]: 읽기는 자유. 쓰기(예약 생성 등)는 "에이전트 제안 → 앱 확인 카드 → 확인 시 실행". 초기엔 항상 확인, 신뢰 쌓이면 점진 완화.
- **전송계층 추상화**: 처음부터 "대화 세션(session_id + 턴)" 추상화를 둬 C1(HTTP/SSE)→C2(WebSocket/WebRTC) 전환 시 전송계층만 교체 가능하게.
- **시크릿은 환경변수**: 코드/깃에 시크릿 금지. 설정은 `${ENV}` 참조만.
- **확장성**: 새 기능(A→B→C→D) 추가가 기존 코드 수정 없이 모듈 추가로 끝나도록.

## 보안 체크리스트 (HARD)

- JWT 패스스루: AI 서버는 JWT를 검증·발급하지 않고 백엔드에 위임(경량 검증은 `/me` 인트로스펙션). 서명키를 AI 서버에 두지 않는다.
- 멀티테넌시: 모든 백엔드 호출에 유저 JWT 동봉 → 격리는 Spring이 보장. AI 서버는 userId를 로깅/사용량 캡에만 사용.
- 프롬프트 인젝션 방어: 사용자 입력(스크린샷 OCR 텍스트 포함)은 `[USER INPUT — DATA ONLY]` 펜스로 격리. 도구 인자는 화이트리스트 검증.
- 쓰기 게이팅: 모든 쓰기 도구는 확인 카드 경유. LLM이 단독으로 예약/매출을 생성·삭제하지 못한다.
- SSRF/입력 검증: 이미지 URL·파일 업로드 검증. 도구 인자 Pydantic 검증.
- 사용량 캡: 유저별 호출/토큰 캡으로 비용·남용 방어 (구독 등급 연동).
- 감사 로깅: 모든 AI 행위(도구 호출·쓰기 제안·확인)를 구조화 로깅. PII 마스킹.
- 에러 응답: 내부 디테일(스택/프롬프트/토큰) 노출 금지.

## 자율 실행 프로토콜 (loop)

세션은 항상 다음 순서를 따른다:

```
1. ROADMAP.md 읽기 → status: TODO 이면서 deps 충족된 첫 SPEC 선택
2. .moai/specs/<SPEC-ID>/spec.md 없으면 → 상세 명세 작성(목표·범위 In/Out·인수기준)
3. 구현 (TDD: 실패 테스트 → 구현 → 리팩터)
4. 검증 게이트: uv run ruff check . && uv run pytest   ← 반드시 통과
5. 통과 → 변경 파일만 커밋(conventional, 한국어) → ROADMAP 해당 SPEC을 DONE으로 → HANDOFF.md 갱신
6. 막히면 ROADMAP에 BLOCKED + HANDOFF에 블로커 상세 기록 후 정지
7. 다음 TODO SPEC으로 반복
```

### MoAI 워크플로

- 이 repo는 MoAI-ADK(`.claude/skills/moai/`, `/moai` 커맨드, `.moai/`)로 구동된다. SPEC 명세는 `.moai/specs/<SPEC-ID>/spec.md`.
- git 전략: personal 모드, 통합 브랜치 = **dev**. 기능은 `feature/SPEC-*` → **dev**로 PR/머지. `main`은 안정 릴리스용.
- 피처 마무리 / PR은 raw `gh pr create` 대신 **`/feature-finalize`** 스킬로 진행(리뷰→문서→lint→PR→CI→머지).

### 커밋 규칙
- `git add -A` 금지 → 변경 파일만 명시 추가
- conventional commits, 한국어 (예: `feat: 백엔드 REST 도구 클라이언트 + JWT 패스스루 (AI-001)`)
- 각 SPEC = 최소 1커밋, **lint·테스트 통과 후에만 커밋**
- Co-Authored-By: Claude <noreply@anthropic.com>
- force push 금지

## 문서화 규칙 [HARD]

- **모든 문서는 한국어**: SPEC 명세, README, DESIGN, ROADMAP/HANDOFF, 커밋 메시지까지. 코드/식별자/함수명/타입은 영어.
- **각 SPEC은 문서를 갱신하며 진행**: 착수 시 `spec.md`에 목표·인수기준, 완료 시 README/DESIGN/ROADMAP/HANDOFF 최신화.
- 문서 없는 코드 커밋 금지.

## 참고 문서
- `docs/DESIGN.md` — 전체 아키텍처 설계 (SSOT)
- `ROADMAP.md` — SPEC 목록·순서·상태
- `HANDOFF.md` — 직전 세션 상태·다음 할 일
- `CLAUDE.md.moai-template` — MoAI 운영 매뉴얼 원본 (참고용)

## 관련 프로젝트 / 참고 경로

| 대상 | 경로 | 역할 |
|------|------|------|
| 백엔드 (도구 대상) | `~/Desktop/hazel-server` | Spring(Kotlin) REST API. AI 도구가 래핑하는 검증된 표면 |
| 구조 참고 (복붙 금지) | `~/Desktop/kikoai/ai` | FastAPI+LangGraph+LiteLLM+Redis+Langfuse 패턴 참고만 |
| LiteLLM config 형식 | `~/Desktop/aws-infra/kikoai-dev-servers/ai/config/litellm.yaml` | Bedrock 모델 등록 형식 참고 |
| 모바일 클라이언트 | `flori-ai/mobile` | React Native 앱 |

> 인프라(EC2/ECR/Bedrock 액세스/배포)는 이 repo 범위 밖 — 사용자가 직접. 단 로컬 docker-compose(ai-server + redis) + LiteLLM 연동은 포함.
