# 코딩 컨벤션

> 이 repo에서 코드를 쓰기 전 읽는다. 보안 1순위(멀티테넌시·쓰기 게이팅) 원칙이 코드 레벨에서 어떻게 강제되는지 정리한다. 전체 설계 근거는 [../DESIGN.md](../DESIGN.md), as-built는 [../ARCHITECTURE.md](../ARCHITECTURE.md).

---

## 1. 도구 등록 (tool registry)

모든 백엔드 호출은 `app/tools/registry.py`에 **등록된 도구를 통해서만** 한다. LLM의 행동공간 = 등록된 도구 = 검증된 API 표면.

- 새 행동이 필요하면 백엔드(`hazel-server`)에 엔드포인트를 먼저 만들고, 여기서 얇게 래핑한다. 이 repo에서 우회 호출 금지.
- 각 도구는 `is_write`로 읽기/쓰기를 **반드시 분류**한다. ReAct 루프는 `is_write=True` 도구의 직접 실행을 차단한다.
- 도구 인자는 Pydantic 스키마로 화이트리스트 검증한다. LLM이 임의 경로·메서드를 호출하지 못한다.
- 인자 오류·백엔드 오류는 예외로 던지지 않고 에러 dict로 돌려 LLM이 self-correction 하도록 한다.

---

## 2. 쓰기 게이팅 (human-in-loop) [HARD]

읽기는 LLM이 자유 호출, **쓰기는 직접 실행 금지**.

- 쓰기 도구는 즉시 실행하지 않고 `PendingWrite`(제안)를 만들어 `ConfirmationCard`로 앱에 반환한다.
- 앱이 카드를 렌더 → 사용자 확인 → `POST /confirm {proposal_id}` → 그 시점에 `app/confirm/executor.py`가 실제 백엔드 쓰기(JWT 동봉)를 실행한다.
- `PendingWrite`는 Redis에 TTL·1회성으로 저장하고 `session_id`/`user_id`에 바인딩한다. 소유자 검증 실패는 403, 미존재/만료는 404.

---

## 3. async I/O

백엔드·LLM·Redis 호출은 **전부 async**다.

- HTTP는 `httpx.AsyncClient`(`app/backend/client.py`), Redis는 async 클라이언트. 블로킹 호출(`time.sleep`, 동기 `requests` 등) 금지.
- `ruff`의 `ASYNC` 룰이 위반을 잡는다. FastAPI 의존성 주입 관용구(`Depends`/`Query`/`Header`/`Path`)는 `flake8-bugbear` 예외로 허용.
- 테스트는 `asyncio_mode = "auto"` (pytest-asyncio). 백엔드 호출은 `respx`, Redis는 `fakeredis`로 격리한다.

---

## 4. 입력 검증 (SSRF·키 오염 방어)

`app/api/validators.py`에서 경계 입력을 검증한다.

- `session_id`·`proposal_id`는 SafeId 형식 검증 — Redis 키 오염 방지.
- 이미지 URL은 SSRF 가드(스킴·호스트 검증)를 통과해야 한다.
- 음성 입력은 오디오 크기 상한(캡)을 둔다. WebSocket은 누적 상한도 둔다.
- 도구 인자·요청 DTO는 Pydantic v2로 검증한다.

---

## 5. 프롬프트 인젝션 격리

사용자/이미지/컨텍스트에서 온 모든 입력(스크린샷 OCR 텍스트 포함)은 시스템 프롬프트에서 `[USER INPUT — DATA ONLY]` 펜스로 격리한다 (`app/agents/prompts.py`, `app/agents/vision.py`).

- 펜스 토큰 자체를 주입하려는 시도를 무력화하도록 처리한다.
- 선제 제안(`app/agents/proactive.py`)의 백엔드 컨텍스트도 데이터로 펜스 격리한다.

---

## 6. Python 스타일 · 린트

- `ruff` — line-length 120, `target-version = py312`, 룰셋 `E / F / I / UP / B / ASYNC`.
- 커밋 전 검증 게이트: `uv run ruff check . && uv run ruff format --check .` (또는 `make lint`). 자동 수정은 `make fmt`.
- 코드·식별자·함수명·타입은 영어, 문서·주석 설명은 한국어(문서화 규칙).
- 비밀값은 코드·깃에 두지 않는다 — env 주입만 (`app/core/config.py`, Pydantic Settings).

---

## 7. 감사 로깅

모든 AI 행위(턴·도구 호출·쓰기 제안/확인/실행)는 `app/core/audit.py`로 구조화 로깅한다.

- PII(전화·이름)와 토큰은 중첩 구조까지 깊게(deep) 마스킹한다.
- 에러 응답에 내부 디테일(스택·프롬프트·토큰)을 노출하지 않는다.
