# SPEC-AI-001 — Foundation (기반 스켈레톤)

> status: DONE · deps: DESIGN 승인(완료) · Phase 1 · 28 tests 통과 · ruff clean

## 목표

Flori AI 서비스의 빈 프로젝트를 부팅 가능한 FastAPI + LangGraph 스켈레톤으로 세운다.
이후 모든 기능 SPEC(A/B/C/D)이 이 골격 위에 도구·노드를 추가하는 것으로 끝나도록, 횡단 관심사(인증·백엔드 클라이언트·세션·LLM·캡·감사)의 자리와 품질 게이트를 마련한다.

## 범위 (In)

- **툴링**: uv 프로젝트(`pyproject.toml`, Python 3.12+), ruff(lint+format, line-length=120), pytest(+pytest-asyncio), `.python-version`.
- **설정**: `app/core/config.py` — Pydantic Settings로 env 로드(LiteLLM/백엔드/Redis URL, 모델명, 캡, TTL). 평문 시크릿 없음.
- **백엔드 REST 클라이언트**: `app/backend/client.py` — httpx async, **유저 JWT 패스스루**(`Authorization: Bearer` 동봉), 타임아웃·재시도, 상태코드→예외 매핑.
- **인증**: `app/backend/auth.py` — `GET /me` 인트로스펙션으로 JWT 검증 + `userId` 추출, 짧은 캐시. FastAPI 의존성으로 보호 라우트에 주입.
- **세션 추상화**: `app/session/models.py`(Session/Turn/Message Pydantic) + `app/session/store.py`(Redis 저장, TTL). 전송계층 독립(session_id + 턴).
- **LLM 연동**: `app/agents/llm_client.py` — LiteLLM 프록시 경유 ChatOpenAI 팩토리(모델 `claude-haiku-4-5`).
- **LangGraph 스켈레톤**: `app/agents/graph.py` — 최소 StateGraph(에이전트 루프는 AI-002). 컴파일/호출 가능.
- **사용량 캡 자리**: `app/core/usage.py` — Redis 카운터 기반 유저별 캡(seam). 초과 시 예외.
- **감사 로깅**: `app/core/audit.py` — 구조화 JSON 이벤트 + PII(전화/이름) 마스킹.
- **API**: `app/api/health.py`(`GET /health`, no auth) + 보호 엔드포인트 1개로 인증 의존성 검증. `app/main.py`(FastAPI + lifespan: Redis 풀).
- **로컬 스택**: `docker-compose.yml`(ai-server + redis), `Dockerfile`, `.env.example`, `litellm-config.yaml`(Claude Haiku 4.5 단일 모델).

## 범위 밖 (Out)

- 실제 도구 카탈로그/에이전트 루프 (→ SPEC-AI-002). 이 SPEC은 LLM·그래프를 "스켈레톤"으로만.
- 비전 OCR(→ B), 음성(→ C), 선제 제안(→ D).
- 인프라/배포(EC2/ECR/Bedrock 액세스). 실제 Bedrock 호출 테스트 없음(클라이언트 구성만 검증).

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 가 모두 통과한다.
2. `GET /health` 가 200과 `{status:"ok", service:"flori-ai"}` 를 반환한다(auth 없음).
3. 보호 엔드포인트가 JWT 없으면 401, 유효 JWT(`/me` 200 mock)면 200을 반환한다.
4. 백엔드 클라이언트가 호출 시 받은 JWT를 `Authorization` 헤더로 그대로 전달한다(respx 검증). 401/5xx를 표준 예외로 매핑한다.
5. `/me` 인트로스펙션이 200→userId, 401→인증예외, 동일 토큰 재호출 시 캐시 히트(백엔드 1회 호출).
6. 세션 스토어가 session_id로 세션 생성/조회 + 턴 append 를 Redis(fakeredis)에서 수행한다.
7. 사용량 캡이 한도 내 통과, 초과 시 예외를 던진다(fakeredis).
8. 감사 로거가 구조화 이벤트를 남기고 전화/이름을 마스킹한다.
9. LLM 클라이언트 팩토리가 config(base_url/model/key)로 구성된다(네트워크 없음).
10. `docker compose config` 가 유효하고, `.env.example`/`litellm-config.yaml`에 평문 시크릿이 없다.

## 설계 메모

- 테스트는 외부 의존을 격리: Redis는 `fakeredis`, 백엔드 HTTP는 `respx`, LLM은 구성만 단언(호출 없음).
- 인증 의존성은 `/me` 결과를 `RequestContext{user_id, jwt}`로 노출 — 도구가 JWT를 패스스루할 단일 출처.
- 캡/감사는 seam 수준(정책 최소) — 정교화는 후속.
- 모든 사용자 입력 격리·쓰기 게이팅은 기능 SPEC에서 구현하되, 모델/자리(`PendingWrite` 등)는 세션 모델에 예약.
