# SPEC-AI-006 — D 에이전트 확장 (선제 제안 + 관측성)

> status: DONE · deps: SPEC-AI-002/003/004(DONE) · Phase 1 · 90 tests 통과 · ruff clean

## 목표

A·B·C로 쌓은 도구·세션 위에, **선제 제안(proactive)** 레이어를 얹는다. 사장님이 묻기 전에 AI가 컨텍스트(오늘 요약·다가오는 예약)를 읽고 다음 할 일을 제안한다(예: "내일 예약 3건 — 리마인더 보낼까요?"). 더불어 에이전트 복잡도가 올라간 만큼 **Langfuse 관측성 seam**(v1 선택, no-op 폴백)을 도입한다.

## 범위 (In)

- **관측성 seam** (`app/observability/tracing.py`): `observe` 데코레이터 — Langfuse env 설정 시 트레이싱, 미설정 시 **함수 동작 보존 no-op 패스스루**. 키 노출/실패가 본 기능을 막지 않음(fail-open). config에 Langfuse env 자리.
- **선제 제안** (`app/agents/proactive.py`): `generate_proactive_suggestions(model, client, ctx) -> list[Suggestion]` — 읽기 API(`/dashboard/today`, `/reservations/upcoming`)로 컨텍스트 수집(JWT 패스스루) → LLM이 구조화 제안(JSON) 생성. 백엔드/파싱 실패는 fail-open(빈 목록). 컨텍스트는 백엔드 데이터(시스템 파생)로 펜스 격리.
- **엔드포인트** (`app/api/proactive.py`): `GET /agent/proactive` — 인증·캡 적용 → `{suggestions: [{title, detail}]}`.
- 핵심 진입점(`run_agent`, `generate_proactive_suggestions`)에 `observe` 적용.

## 범위 밖 (Out)

- C2 실시간(보류). 인-챗에서 예약 제안 도구(propose_reservation)를 ReAct 루프에 추가하는 것은 후속(현재 B는 `/ocr`+`/confirm`으로 동작).
- 실제 Langfuse 서버 연동·대시보드(인프라). 테스트는 no-op 폴백 + fake model + respx.
- 제안의 자동 실행 — 제안은 표시일 뿐, 쓰기는 여전히 confirm 경유(human-in-loop).

## 인수 기준

1. `uv run ruff check . && uv run ruff format --check . && uv run pytest` 통과.
2. `observe`: Langfuse 미설정 시 데코레이트된 async 함수가 인자/반환/예외를 그대로 보존한다(no-op).
3. `generate_proactive_suggestions`: 컨텍스트 읽기에 JWT를 패스스루하고(respx), fake model의 제안 JSON을 `list[Suggestion]`로 파싱한다. 백엔드 오류/비-JSON이면 빈 목록(fail-open).
4. `GET /agent/proactive`: 미인증 401. 유효 시 200 + `{suggestions: [...]}`.
5. 제안 컨텍스트(백엔드 데이터)가 LLM 프롬프트에서 데이터로 격리된다(지시 주입 방지).
6. 제안은 읽기전용 — 어떤 쓰기도 직접 실행하지 않는다.

## 설계 메모

- 선제 제안은 A의 읽기 도구를 "묶어" 컨텍스트를 만들고 LLM이 해석 — A·B·C 위의 오케스트레이션 확장.
- 관측성은 seam만(no-op 폴백) — 실 Langfuse는 env로 켜지며, 키 부재/오류가 기능을 막지 않는다(fail-open).
- 제안→실행은 항상 human-in-loop(B의 confirm) — 선제 제안도 쓰기를 자동 실행하지 않는다.
