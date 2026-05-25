# SPEC-AI-002 — A 데이터 분석 (읽기전용 도구콜 루프)

> status: DONE · deps: SPEC-AI-001(DONE) · Phase 1 · 41 tests 통과 · ruff clean

## 목표

"이번 달 매출 왜 떨어졌어?" 같은 질의에, 백엔드 통계/매출/고객 **읽기 API를 도구로 호출**해 수치를 모은 뒤 LLM이 근거 있는 해설을 생성한다.
가장 저렴·저위험(쓰기 없음)인 A를 먼저 만들어 **도구콜 루프(ReAct)를 끝까지 검증**한다. 이후 B/C/D가 이 루프 위에 도구를 추가한다.

## 범위 (In)

- **읽기 도구 레지스트리** (`app/tools/registry.py`): `ToolSpec`(name·description·Pydantic args·is_write·handler) + 단일 `REGISTRY`. 핸들러는 `BackendClient` + `RequestContext`로 백엔드 호출(JWT 패스스루). OpenAI 함수-툴 스키마 생성 + 인자 검증 + 디스패치.
  - 초기 도구(읽기전용): `get_month_dashboard(month?)`→`/dashboard/month`, `get_today_dashboard()`→`/dashboard/today`, `list_sales(month?)`→`/sales`, `list_customers()`→`/customers`.
- **ReAct 루프** (`app/agents/react_loop.py`): `run_agent(model, client, ctx, user_text, history?, max_iterations)` — LLM `bind_tools` → tool_calls 디스패치 → ToolMessage 누적 → 최종 응답. iteration cap, 인자 검증 실패 시 self-correction(에러를 ToolMessage로), 도구 호출 감사 로깅.
- **시스템 프롬프트** (`app/agents/prompts.py`): 꽃집 데이터 분석가 페르소나(한국어). 사용자 입력은 `[USER INPUT — DATA ONLY]` 펜스로 격리. "쓰기 도구 없음 — 읽기·해설만" 명시.
- **채팅 엔드포인트** (`app/api/chat.py`): `POST /chat` — 인증(`get_request_context`) → 세션 get_or_create + 유저 턴 기록 → 에이전트 실행 → 어시스턴트 턴 기록 → `{reply, session_id}`. `chat_model`은 lifespan에서 `build_chat_model`로 구성.

## 범위 밖 (Out)

- 쓰기/예약 생성(→ B), 비전 OCR(→ B), 음성(→ C), 선제 제안(→ D).
- 실제 Bedrock 호출(테스트는 fake chat model + respx 백엔드). LiteLLM 실연동은 런타임/인프라.
- 도구 카탈로그 전체(추가 읽기 도구는 후속 확장).

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 통과.
2. 레지스트리: 등록된 도구가 OpenAI 함수-툴 스키마로 직렬화되고, 전부 `is_write=False`(읽기전용)이다.
3. 디스패치: 도구 호출이 `BackendClient`에 받은 JWT를 패스스루하고 백엔드 응답을 반환한다(respx). 잘못된 인자는 예외 대신 구조화 에러를 돌려 self-correction을 가능케 한다.
4. ReAct 루프: fake model이 (a) 도구 호출 → (b) 최종 답변을 스크립트하면, 루프가 도구를 디스패치하고 최종 텍스트를 반환한다. 도구를 무한 반복하는 model에는 `max_iterations`에서 멈춘다.
5. 루프가 각 도구 호출을 감사 로깅한다(`tool_call` 이벤트, user_id 포함).
6. `POST /chat`: JWT 없으면 401, 유효 JWT면 200 + `{reply, session_id}`. 세션에 유저/어시스턴트 턴이 기록된다(fakeredis).
7. 사용자 입력이 프롬프트에 `[USER INPUT — DATA ONLY]` 펜스로 격리된다.

## 설계 메모

- 도구 = 백엔드 검증된 표면의 얇은 래퍼 — 행동공간을 API로 한정. `userId`는 백엔드가 JWT로 주입하므로 도구 인자에 없음.
- 루프는 LangChain `BaseChatModel` 인터페이스(`bind_tools`/`ainvoke`) 기준. 테스트는 스크립트형 fake model 주입으로 결정적 검증(실 LLM 비의존).
- 디스패치는 `REGISTRY`의 Pydantic args로 LLM 인자를 검증·캐스팅 — 타입 실수로 루프가 헛돌지 않게.
- 읽기 전용이라 human-in-loop 게이팅 불필요(쓰기 도구 도입은 B). is_write 플래그·디스패치 가드는 미리 자리 마련.
