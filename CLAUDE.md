# CLAUDE.md

이 파일은 Claude Code가 이 프로젝트에서 작업할 때 참조하는 가이드입니다. **본 파일이 이 repo의 SSOT 지침이다.**

---

## 프로젝트 개요

**Flori AI** — Flori(꽃집 SaaS)의 프리미엄 AI 기능을 담당하는 **별도 AI 서비스**. FastAPI + LangGraph.
자매 repo: `flori-ai/server`(Spring 백엔드 = `~/Desktop/hazel-server`), `flori-ai/mobile`(React Native 앱), `flori-ai/web`.

꽃집 사장(1인 운영, 손이 바쁨)을 위한 AI 기능을 제공한다. **백엔드 DB에 직접 접근하지 않고**, 기존 Spring REST API(`hazel-server`)를 도구로 호출하는 얇은 AI 오케스트레이션 레이어다.

- **A 데이터 분석**: "이번 달 매출 왜 떨어졌어?" → 백엔드 통계 API를 도구로 읽어 LLM이 해설 (읽기전용)
- **B OCR→예약**: 카톡 대화 스크린샷 → 비전 LLM이 고객·날짜·시간·품목·금액 추출 → 예약 후보 → 사용자 확인 → 예약 생성
- **C 음성**: 음성 지시 → STT → 에이전트 도구 호출 → 음성 응답 (C1 푸시투토크 → C2 실시간)
- **D 에이전트**: A·B·C 도구를 묶어 다단계·선제 제안하는 에이전트로 확장

---

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

---

## 프로젝트 구조

```
app/
├── main.py             # FastAPI 앱 + lifespan(자원 구성) + 라우터 등록
├── api/                # 전송: health, whoami, chat, ocr, confirm, voice, voice_ws, proactive, deps, validators
├── agents/             # react_loop(ReAct 루프), prompts, llm_client, vision, proactive, graph(스켈레톤)
├── tools/              # registry — 백엔드 읽기 도구 + 디스패치 + OpenAI 스키마
├── backend/            # client(httpx, JWT 패스스루), auth(/me 인트로스펙션)
├── session/            # models(Session/Turn/PendingWrite), store(Redis)
├── confirm/            # models(ReservationDraft/ConfirmationCard), store(PendingWriteStore), executor
├── voice/              # ports(STT/TTS Protocol), pipeline(run_voice_turn), aws(Transcribe/Polly)
├── core/               # config, usage(캡), audit(감사), errors
├── observability/      # tracing(@observe, Langfuse seam)
└── models/             # 공유 DTO
```

레이어: `api(전송) → agents(오케스트레이션) → tools(백엔드 래퍼) → backend(REST 클라이언트)` + 횡단(session/confirm/voice/core/observability). `hazel-server`의 `controller → service → repository`에 대응하며 **DB 레이어 없음** — 영속은 전부 백엔드, AI는 Redis(휘발성 세션·캡)만 소유.

---

## 아키텍처 원칙 (HARD)

- **게이트웨이 뒤 stateless** [HARD]: ai-server는 web/모바일이 직접 호출하지 않는다. **Spring 서버(게이트웨이)만** 내부망에서 호출한다 — `X-Internal-Key`(게이트웨이 신뢰) + `X-User-Id` + 유저 JWT(도구 호출 패스스루용)를 붙여서. 대화 세션·메시지·쓰기 제안의 **영속/로깅은 게이트웨이 DB(Postgres)가 소유**하고, ai-server는 무상태다(채팅 히스토리는 매 요청 `messages`로 받음). 자세한 게이트웨이 계약은 [`server`(hazel-server) `/ai/*`] 참조.
- **멀티테넌시 = 보안 1순위** [HARD]: 게이트웨이가 유저 JWT를 검증하고, ai-server는 받은 JWT를 **그대로 백엔드 REST 도구 호출에 패스스루**한다. user_id 격리·구독 게이팅은 Spring이 강제한다. **AI에 god-mode DB 커넥션을 주지 않는다.**
- **도구(tool) = 백엔드 기존 REST 엔드포인트의 얇은 래퍼**: 에이전트의 행동공간 = 이미 검증된 API 표면. 새 행동이 필요하면 백엔드에 엔드포인트를 먼저 만든다(이 repo에서 우회 금지).
- **쓰기는 human-in-loop** [HARD]: 읽기는 자유. 쓰기(예약 생성)는 "ai-server가 초안 추출 → **게이트웨이가** 확인 카드(제안) 보관 → 사용자 확인 시 **게이트웨이가** 예약 생성". LLM 단독 쓰기 불가. (ai-server는 추출만 — `/ocr/reservation`이 draft만 반환, `/confirm`은 게이트웨이 소유.)
- **전송계층 추상화**: 처음부터 "대화 세션(session_id + 턴)" 추상화를 둬 C1(HTTP/SSE)→C2(WebSocket/WebRTC) 전환 시 전송계층만 교체 가능하게.
- **시크릿은 환경변수**: 코드/깃에 시크릿 금지. 설정은 `${ENV}` 참조만.
- **확장성**: 새 기능(A→B→C→D) 추가가 기존 코드 수정 없이 모듈 추가로 끝나도록.

---

## 보안 체크리스트 (HARD)

- 게이트웨이 신뢰: ai-server는 유저 JWT를 직접 검증하지 않고 **`X-Internal-Key`(게이트웨이만 보유)로 신뢰**한다(타이밍 세이프 비교). `X-User-Id`로 테넌트 식별, 유저 JWT는 백엔드 도구 호출에 패스스루. JWT 검증·발급·서명키는 게이트웨이/백엔드 몫.
- 멀티테넌시: 모든 백엔드 호출에 유저 JWT 동봉 → 격리는 Spring이 보장. AI 서버는 userId를 로깅에만 사용(사용량 캡은 게이트웨이가 소유).
- 프롬프트 인젝션 방어: 사용자 입력(스크린샷 OCR 텍스트 포함)은 `[USER INPUT — DATA ONLY]` 펜스로 격리. 도구 인자는 화이트리스트 검증.
- 쓰기 게이팅: 모든 쓰기 도구는 확인 카드 경유. LLM이 단독으로 예약/매출을 생성·삭제하지 못한다.
- SSRF/입력 검증: 이미지 URL·파일 업로드 검증. 도구 인자 Pydantic 검증.
- 사용량 캡: 유저별 호출/토큰 캡으로 비용·남용 방어 (구독 등급 연동).
- 감사 로깅: 모든 AI 행위(도구 호출·쓰기 제안·확인)를 구조화 로깅. PII 마스킹. 토큰 사용량(`llm_usage`)은 숫자만 기록(PII 아님).
- 관측성(Langfuse): `@observe` 트레이싱을 켜면(`LANGFUSE_PUBLIC_KEY` + langfuse 설치) LLM 입출력 원문(사용자 발화·이미지 URL·고객 PII 가능)이 트레이스로 전송된다. `audit.py`의 마스킹은 트레이스 경로엔 적용되지 않으므로, **반드시 self-host Langfuse(현재 `langfuse.flori.ai.kr`) 사용 + PII scrubbing 검토 후 활성화**한다. 외부 SaaS Langfuse로 마스킹 없이 보내지 않는다.
- 에러 응답: 내부 디테일(스택/프롬프트/토큰) 노출 금지.

---

## 코딩 컨벤션

> **상세 내용과 코드 예시는 [`docs/conventions/26-05-28-coding-conventions.md`](docs/conventions/26-05-28-coding-conventions.md) 참조**

| 컨벤션 | 핵심 규칙 |
|--------|-----------|
| 도구 등록 | 모든 백엔드 호출은 `app/tools/registry.py`에 등록된 도구만. `is_write` 분류 필수, 인자는 Pydantic 스키마로 화이트리스트 검증 |
| 쓰기 게이팅 | 쓰기 도구는 직접 실행 금지 → `PendingWrite` 제안 + `ConfirmationCard` 반환 → `/confirm` 경유 |
| async I/O | 백엔드·LLM·Redis 호출은 전부 async(httpx async, `ruff ASYNC` 룰). 블로킹 호출 금지 |
| 입력 검증 | `session_id`/`proposal_id`는 SafeId, 이미지 URL SSRF 가드, 오디오 크기 캡 (`app/api/validators.py`) |
| 프롬프트 격리 | 사용자/이미지/컨텍스트 입력은 `[USER INPUT — DATA ONLY]` 펜스로 격리 |
| 린트/포맷 | `ruff` (line-length 120, py312, `E/F/I/UP/B/ASYNC`). 커밋 전 `uv run ruff check . && uv run ruff format --check .` |

---

## 주요 파일 위치

| 용도 | 위치 |
|------|------|
| FastAPI 앱 + lifespan | `app/main.py` |
| 게이트웨이 신뢰 인증(X-Internal-Key·X-User-Id) | `app/api/deps.py` (`get_request_context`) |
| JWT 패스스루 클라이언트 | `app/backend/client.py` |
| `/me` 인트로스펙션(레거시·voice 등) | `app/backend/auth.py` |
| ReAct 루프 | `app/agents/react_loop.py` (`run_agent`) |
| 시스템 프롬프트·펜스 | `app/agents/prompts.py` |
| LLM 팩토리(LiteLLM) | `app/agents/llm_client.py` |
| 비전 OCR 추출 | `app/agents/vision.py` |
| 선제 제안 | `app/agents/proactive.py` |
| 도구 레지스트리 | `app/tools/registry.py` |
| 쓰기 실행기(게이트웨이 confirm에서 재사용 가능) | `app/confirm/executor.py` (`/confirm` 라우트는 게이트웨이로 이전됨) |
| 음성 파이프라인 | `app/voice/pipeline.py`, `app/voice/aws.py`, `app/voice/ports.py` |
| 세션 스토어(Redis) | `app/session/store.py`, `app/session/models.py` |
| 설정/캡/감사 | `app/core/config.py`, `app/core/usage.py`, `app/core/audit.py` |
| 관측성 seam | `app/observability/tracing.py` |

---

## 자율 실행 프로토콜 (loop)

세션은 항상 다음 순서를 따른다:

```
1. ROADMAP.md 읽기 → status: TODO 이면서 deps 충족된 첫 SPEC 선택
2. docs/specs/<SPEC-ID>.md 없으면 → 상세 명세 작성(목표·범위 In/Out·인수기준)
3. 구현 (TDD: 실패 테스트 → 구현 → 리팩터)
4. 검증 게이트: uv run ruff check . && uv run pytest   ← 반드시 통과
5. 통과 → 변경 파일만 커밋(conventional, 한국어) → ROADMAP 해당 SPEC을 DONE으로 → HANDOFF.md 갱신
6. 막히면 ROADMAP에 BLOCKED + HANDOFF에 블로커 상세 기록 후 정지
7. 다음 TODO SPEC으로 반복
```

### 워크플로

- SPEC 명세는 `docs/specs/<SPEC-ID>.md`에 둔다.
- git 전략: 통합 브랜치 = **dev**. 기능은 `feature/SPEC-*` → **dev**로 PR/머지. `main`은 안정 릴리스용.
- 피처 마무리 / PR은 raw `gh pr create` 대신 **`/feature-finalize`** 스킬로 진행(리뷰→문서→lint→PR→CI→머지).

### 커밋 규칙
- `git add -A` 금지 → 변경 파일만 명시 추가
- conventional commits, 한국어 (예: `feat: 백엔드 REST 도구 클라이언트 + JWT 패스스루 (AI-001)`)
- 각 SPEC = 최소 1커밋, **lint·테스트 통과 후에만 커밋**
- Co-Authored-By: Claude <noreply@anthropic.com>
- force push 금지

---

## 문서화 규칙 [HARD]

- **모든 문서는 한국어**: SPEC 명세, README, DESIGN, ROADMAP/HANDOFF, 커밋 메시지까지. 코드/식별자/함수명/타입은 영어.
- **각 SPEC은 문서를 갱신하며 진행**: 착수 시 `spec.md`에 목표·인수기준, 완료 시 README/DESIGN/ROADMAP/HANDOFF 최신화.
- 문서 없는 코드 커밋 금지.

---

## 참고 문서

```
docs/
├── ARCHITECTURE.md         # as-built 전체 아키텍처 (토폴로지·엔드포인트·레이어·보안·스택)
├── DESIGN.md               # 설계 결정·근거 + 탈락 후보 (SSOT)
├── conventions/            # 코딩 컨벤션 (작업 전 필독)
├── features/               # 기능별(A·B·C·D) 아키텍처·플로우·스택
└── specs/                  # SPEC별 명세·인수기준 (<SPEC-ID>.md)
```

- `ROADMAP.md` — SPEC 목록·순서·상태
- `HANDOFF.md` — 직전 세션 상태·다음 할 일

### docs 파일명 컨벤션

- 날짜성 문서(`docs/conventions/`·`docs/features/` 등): `yy-mm-dd-{설명}.md`
  - 예: `26-05-28-coding-conventions.md`, `26-05-26-A-data-analysis.md`
  - 설명은 다른 문서와 구분될 정도로 구체적으로 작명 (기능 문서는 `A·B·C·D` 식별자를 설명 앞에 유지)
- `docs/specs/`: SPEC ID 그대로 `<SPEC-ID>.md` (예: `SPEC-AI-002.md`)
- 상시(evergreen) 문서만 네이밍 그대로 유지: `docs/ARCHITECTURE.md` · `docs/DESIGN.md`

---

## 관련 프로젝트 / 참고 경로

| 대상 | 경로 | 역할 |
|------|------|------|
| 백엔드 (도구 대상) | `~/Desktop/hazel-server` | Spring(Kotlin) REST API. AI 도구가 래핑하는 검증된 표면 |
| 구조 참고 (복붙 금지) | `~/Desktop/kikoai/ai` | FastAPI+LangGraph+LiteLLM+Redis+Langfuse 패턴 참고만 |
| LiteLLM config 형식 | `~/Desktop/aws-infra/kikoai-dev-servers/ai/config/litellm.yaml` | Bedrock 모델 등록 형식 참고 |
| 모바일 클라이언트 | `flori-ai/mobile` | React Native 앱 |

> 인프라(EC2/ECR/Bedrock 액세스/배포)는 이 repo 범위 밖 — 사용자가 직접. 단 로컬 docker-compose(ai-server + redis) + LiteLLM 연동은 포함.
