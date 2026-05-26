# 기능별 아키텍처 문서

각 기능의 as-built 상세(개요·스택·레이어·플로우·핵심 포인트). 전체 그림은 [../ARCHITECTURE.md](../ARCHITECTURE.md), 설계 결정·근거는 [../DESIGN.md](../DESIGN.md).

| 문서 | 기능 | 엔드포인트 | 핵심 |
|------|------|-----------|------|
| [A-data-analysis.md](A-data-analysis.md) | A 데이터 분석 | `POST /chat` | 읽기 도구콜 루프 + LLM 해설 (읽기전용) |
| [B-ocr-reservation.md](B-ocr-reservation.md) | B OCR→예약 | `POST /ocr/reservation` → `POST /confirm` | 비전 추출 → 확인 카드 → 예약 생성 (human-in-loop) |
| [C-voice.md](C-voice.md) | C 음성 | `POST /voice/turn`, `WS /voice/stream` | STT→에이전트→TTS, C1 HTTP / C2 WebSocket |
| [D-agent.md](D-agent.md) | D 에이전트 확장 | `GET /agent/proactive` | 선제 제안 + Langfuse 관측성 seam |

> 공통: 모든 기능은 인증(`/me` 패스스루) + 사용량 캡을 거치고, 쓰기는 confirm(human-in-loop) 경유, 에이전트는 읽기전용. 자세한 공통 사항은 [../ARCHITECTURE.md](../ARCHITECTURE.md) §4·§5.
