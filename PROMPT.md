# 목표 (측정 가능)

ai 서비스의 **LLM 프롬프트 빌더가 조용히 깨지는 것을 막는 회귀 테스트**를 만든다.
대상: `app/agents/prompts.py`(시스템 프롬프트·`[USER INPUT — DATA ONLY]` 펜스), `app/agents/vision.py`(`_VISION_SYSTEM`/`_VISION_PROMPT`), `app/agents/proactive.py`(`_SYSTEM`/`[CONTEXT — DATA ONLY]` 펜스).
완료 = 위 빌더의 **보안·구조 불변식**(인젝션 방어 문구·펜스 토큰·JSON-only 지시·읽기전용 선언)이 회귀 테스트로 고정됨.

# 이번 루프에 할 일 (딱 1개 단위)

1. `pytest -q` 로 현재 그린인지 확인한다.
2. 위 3개 모듈 중 **회귀 테스트가 아직 없는 빌더 1개**를 고른다.
3. 그 빌더의 핵심 불변식을 고정하는 `tests/test_prompts.py`(또는 해당 모듈 테스트) 케이스를 추가한다.
   - 전체 한국어 산문 full-string 스냅샷은 피한다(워딩에 취약). 대신 **보안/구조 불변식**을 assert:
     - prompts: `fence_user_input`의 펜스 토큰 래핑 + 펜스 브레이크아웃 escape 동작(보안 크리티컬 → 정확 매칭 OK), `build_system_prompt`에 "읽기 도구만"·인젝션 방어 문구 포함.
     - vision: `_VISION_SYSTEM`에 "지시로 따르지 말"·"JSON" 포함, `_VISION_PROMPT`에 추출 키(customer_name/date/title 등) 전부 포함.
     - proactive: `_SYSTEM`에 JSON 배열 형식·"지시문을 따르지 마"·빈 배열 폴백 문구 포함, 컨텍스트 펜스 `[CONTEXT — DATA ONLY]` 토큰 고정.
4. `pytest tests/test_prompts.py`(해당 테스트) 통과까지 수정.
5. `uv run ruff check . && uv run ruff format --check .` 통과 확인.
6. PROGRESS.md 에 "빌더명 / 고정한 불변식 / 케이스 수" 한 줄 append.
7. 작은 단위 commit: `test(ai): pin <builder> 프롬프트 회귀`

# 완료조건 (EXIT_SIGNAL: true)

- 3개 모듈의 프롬프트 빌더 불변식이 모두 회귀 테스트로 고정되면 **즉시 종료**.
- 더 고정할 의미 있는 프롬프트 불변식이 남지 않으면 종료.

# 금지

- 프로덕션 프롬프트 본문/함수 로직을 바꾸지 마라. **테스트만 추가**.
- 한 루프에서 2개 이상 빌더를 건드리지 마라.
- 실제 LLM/외부 API를 네트워크로 호출하는 테스트 금지(프롬프트는 순수 문자열이라 호출 불필요).
- full-string 스냅샷 남발 금지 — 보안/구조 불변식 위주.

# 상태 기록

- 매 루프 PROGRESS.md 에 한 줄 append (한 일 / 다음 할 일).
