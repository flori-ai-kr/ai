# PROGRESS — 프롬프트 회귀 테스트 (auto/prompt-regression)

> autonomous 루프 상태 기록. 매 iteration 한 줄 append.

- 베이스라인: pytest 84 passed / cov 88%. 프롬프트 빌더 전용 회귀 테스트 없음(`test_prompts.py` 부재).
- iter1: `test_prompts.py` 신설 — prompts(build_system_prompt·fence_user_input 펜스 래핑/브레이크아웃 escape/빈입력)·vision(_VISION_SYSTEM 인젝션방어+JSON-only, _VISION_PROMPT 추출키 6종)·proactive(_SYSTEM JSON배열·인젝션방어·빈배열폴백) 불변식 고정. **+7 케이스 → 91 passed**. 다음: proactive 인라인 펜스 `[CONTEXT — DATA ONLY]` 토큰은 함수 내부라 미고정 → mock 호출로 메시지 검증하는 케이스 추가 검토.
- iter2: `test_proactive.py` 에 `_CapturingModel` + `test_proactive_fences_backend_context_as_data` 추가 — 백엔드 컨텍스트가 `[CONTEXT — DATA ONLY]` 펜스로 격리되고 시스템 메시지가 `_SYSTEM` 임을 고정. **+1 케이스 → 92 passed**. **EXIT_SIGNAL: 3개 모듈 프롬프트 빌더 불변식 모두 고정 — 루프 종료.**
