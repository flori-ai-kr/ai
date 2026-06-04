# ai — best-practice 개선 세션 (2026-06-04)

> 출처: "레포별 개선 프롬프트 팩" §4 `ai` · 브랜치: `improve/ai-best-practice` · 기준: dev

프롬프트 팩의 ai 4개 축(A 비용/캐싱 · B 관측성 · C 안정성 · D LangGraph 평가)을 한 세션에서
처리했다. **핵심 전제: 팩의 gap 일부는 2026-06-04 stateless 게이트웨이 전환(PR #7)으로
이미 무효(stale)**다 — 아래에 축별로 "구현 / 보류(이유)"를 명시한다.

---

## 적용한 개선 (구현)

| 축 | 변경 | 커밋 |
|----|------|------|
| C | 한 턴 독립 tool_calls 병렬화(`asyncio.gather`) | `perf(ai): ...병렬화` |
| C | 비전 OCR·선제제안 `with_structured_output` + 수제 파서 폴백 | `refactor(ai): ...구조화 출력` |
| C | 툴 description 사용시점·반환·예시 + `Field(examples)` | `feat(ai): ...툴 description` |
| B | LLM 토큰 `usage_metadata` 감사 로깅 + `@observe` 확대(vision/voice) + langfuse optional 의존성 | `feat(ai): ...토큰 usage` |
| D | LangGraph 채택 평가 문서 | 본 커밋(문서) |

검증: 각 커밋 `ruff check` + `pytest` 그린. 세션 종료 시 **pytest 98 → (추가 케이스 포함) passed**, ruff clean.

---

## 보류/스킵한 gap과 이유 (faithful report)

### ai-A — 비용/캐싱: 대부분 stale / 부적합

| 팩 gap | 판정 | 이유 |
|--------|------|------|
| 사용량 캡 전 엔드포인트 적용 | **보류(stale)** | 2026-06-04 리팩터로 ai-server는 **stateless**, **캡은 게이트웨이 소유**(`deps.py` 주석·HANDOFF). `/chat` 등에 캡을 다시 넣는 것은 의도적으로 제거한 서버측 강제를 부활시키는 역행. |
| (관련) `voice_ws.py`만 캡 enforce | **그대로 둠(기록)** | 음성 경로는 아직 stateful(Redis 세션). 보호를 자율로 제거하는 건 위험 → 게이트웨이가 음성까지 커버하면 일관화 결정 필요. |
| Prompt Cache(`cache_control`) | **보류(부적합)** | 시스템 프롬프트 ~200토큰 + 툴 소량 → Anthropic 최소 캐시 임계(Haiku ~2048 / Sonnet ~1024 토큰) 미달. 캐시 이득 0. 시스템+툴 묶음이 임계 초과로 커질 때(예: few-shot/툴 카탈로그 확대) 재검토. |
| LiteLLM 폴백/멀티리전 + 토큰기반 캡 | **범위 밖(infra)** | CLAUDE.md: 인프라는 사용자 담당. 배포 LiteLLM은 이미 Sonnet alias + `num_retries:2`(HANDOFF). repo의 `litellm-config.yaml`은 dev 전용. |

### ai-C — 안정성: 전부 구현 (위 표)
- 단, 구조화 출력은 **라이브 Bedrock 미검증**이라 수제 파서 폴백을 함께 둠(안전망). 인젝션 펜스·`extra=forbid`·필드 검증 불변식 유지.

### ai-B — 관측성: 구현 (단, 의존성은 optional)
- 운영 트레이싱은 **현재 LiteLLM `success_callback`(프록시단)**이 담당(HANDOFF). 앱단 `@observe`는
  보조 seam — langfuse를 **하드 의존성이 아닌 optional extra**로 선언해 런타임 이미지 비대화를 피했다.
- 토큰 usage 로깅은 langfuse와 무관하게 항상 동작(audit `llm_usage`).

### ai-D — 평가만 (구현 X)
- [26-06-04-ai-langgraph-adoption-evaluation.md](26-06-04-ai-langgraph-adoption-evaluation.md): 결론 **조건부 보류**.

---

## 후속 권고 (별도 PR)
- `docs/ARCHITECTURE.md`(2026-05-28)는 게이트웨이 전환 이전 상태(/me·/confirm·캡 수명주기)를 일부 반영 — 최신화 필요.
- `app/agents/graph.py`(echo 스켈레톤)·`app/confirm/executor.py`(dead code) 정리.
- 음성 경로 캡/세션 소유권의 게이트웨이 일관화 결정.
