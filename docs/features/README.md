# 기능별 아키텍처 문서

각 기능의 as-built 상세(개요·스택·레이어·플로우·핵심 포인트). 전체 그림은 [../ARCHITECTURE.md](../ARCHITECTURE.md), 설계 결정·근거는 [../DESIGN.md](../DESIGN.md).

| 문서 | 기능 | 엔드포인트 | 핵심 |
|------|------|-----------|------|
| [26-05-26-A-data-analysis.md](26-05-26-A-data-analysis.md) | A 데이터 분석 | `POST /chat` | 읽기 도구콜 루프 + LLM 해설 (읽기전용) |
| [26-05-26-B-ocr-reservation.md](26-05-26-B-ocr-reservation.md) | B OCR→예약 | `POST /ocr/reservation` → `POST /confirm` | 비전 추출 → 확인 카드 → 예약 생성 (human-in-loop) |
| [26-05-26-C-voice.md](26-05-26-C-voice.md) | C 음성 | `POST /voice/turn`, `WS /voice/stream` | STT→에이전트→TTS, C1 HTTP / C2 WebSocket |
| [26-05-26-D-agent.md](26-05-26-D-agent.md) | D 에이전트 확장 | `GET /agent/proactive` | 선제 제안 + Langfuse 관측성 seam |
| [26-06-04-ai-best-practice-session.md](26-06-04-ai-best-practice-session.md) | best-practice 개선 세션 | — | 4축(A·B·C·D) 개선 결과·보류 판정 |
| [26-06-04-ai-langgraph-adoption-evaluation.md](26-06-04-ai-langgraph-adoption-evaluation.md) | ai-D LangGraph 채택 평가 | — | 전환 trade-off·트리거 조건 (결론: 조건부 보류) |
| [26-06-19-M-marketing-blog.md](26-06-19-M-marketing-blog.md) | M 마케팅 블로그 (출시 헤드라인) | `POST /marketing/blog` | 사진+키워드 → 네이버 GEO 블로그 초안 (few-shot 말투·매장맥락, **RAG 아님**) |

> 공통: 모든 기능은 인증(`/me` 패스스루) + 사용량 캡을 거치고, 쓰기는 confirm(human-in-loop) 경유, 에이전트는 읽기전용. 자세한 공통 사항은 [../ARCHITECTURE.md](../ARCHITECTURE.md) §4·§5.
>
> ⚠ 2026-06-04 게이트웨이 stateless 전환(PR #7) 이후 인증(`/me`→내부키 신뢰)·캡(게이트웨이 소유)·`/confirm`(게이트웨이 이동)이 바뀌었다. 위 표·아래 본문 중 일부는 전환 이전 표기 — 최신 상태는 [../../HANDOFF.md](../../HANDOFF.md) 참조.
