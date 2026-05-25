# flori-ai

Flori 꽃집 SaaS의 프리미엄 AI 서비스 — FastAPI + LangGraph. 카톡 스크린샷을 붙여넣으면 예약이 잡히고, "이번 달 매출 왜 떨어졌어?"에 답하고, 말로 예약을 건다.

바쁜 1인 꽃집 사장을 위한 AI 비서. **백엔드 DB에 직접 접근하지 않고**, 기존 Spring REST API(`flori-ai/server`)를 LangGraph 도구로 호출하는 얇은 오케스트레이션 레이어다. 멀티테넌시·구독 게이팅은 유저 JWT를 백엔드에 그대로 전달해 Spring이 강제한다.

LLM/Vision은 **LiteLLM 프록시 → AWS Bedrock Claude Haiku 4.5**(멀티모달) 단일 모델로 처리.

상세 문서:
- [docs/DESIGN.md](docs/DESIGN.md) — 전체 아키텍처·보안 모델·도구 카탈로그·대화 세션 (SSOT)
- [ROADMAP.md](ROADMAP.md) — SPEC 목록·순서·상태
- [HANDOFF.md](HANDOFF.md) — 직전 세션 상태·다음 할 일
- [CLAUDE.md](CLAUDE.md) — 자율 실행 프로토콜·스택·보안 체크리스트

## 기능 (시퀀싱)

| 단계 | 기능 | 설명 |
|------|------|------|
| **A** | 데이터 분석 | 통계 API를 읽어 매출/예약 추이를 LLM이 해설 (읽기전용) |
| **B** | OCR→예약 | 카톡 스크린샷 → 비전 LLM 추출 → 확인 카드 → 예약 생성 |
| **C** | 음성 | 음성 지시 → STT → 에이전트 → 음성 응답 (C1 푸시투토크 → C2 실시간) |
| **D** | 에이전트 | A·B·C 도구를 묶은 다단계·선제 제안 에이전트 |

## 책임 분리

| 레이어 | 책임 |
|--------|------|
| **flori-ai/ai (이 프로젝트)** | AI 오케스트레이션 — 도구콜 루프, 비전 OCR, 음성 세션, 확인 카드, 사용량 캡, 감사 로깅 |
| flori-ai/server (`hazel-server`) | Spring REST API. 데이터 SSOT, 멀티테넌시·구독 게이팅, user_id 격리. AI 도구가 래핑하는 검증된 표면 |
| flori-ai/mobile | React Native 앱. JWT 발급 주체, 확인 카드 UI, 음성 입출력 |
| LiteLLM → Bedrock | Claude Haiku 4.5 (텍스트 + Vision). 프록시 경유 단일 진입점 |

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프레임워크 | FastAPI + uvicorn |
| 에이전트 | LangGraph (StateGraph / ReAct) |
| LLM·Vision | LiteLLM proxy → Bedrock Claude Haiku 4.5 |
| 스키마 | Pydantic v2 |
| HTTP | httpx (async) |
| 세션·캐시 | Redis |
| 트레이싱 | Langfuse (v1 선택) |
| 패키지 | uv |
| 린트·테스트 | ruff / pytest |

## 개발 명령어 (AI-001 이후)

```bash
uv sync                                              # 의존성 설치
uv run uvicorn app.main:app --reload --port 8000     # 로컬 실행
uv run ruff check . && uv run ruff format .          # 린트 + 포맷
uv run pytest                                        # 테스트
docker compose up -d                                 # 로컬 스택 (ai-server + redis)
```

## 인증

AI 서버는 JWT를 발급·서명검증하지 않는다. 클라이언트(앱)가 백엔드에서 발급받은 유저 JWT를 AI 서버에 전달하면, AI 서버는 이를 백엔드 REST 호출에 **그대로 동봉**한다. 격리·게이팅은 Spring이 보장한다. ([docs/DESIGN.md](docs/DESIGN.md) §보안 모델)

> 인프라(EC2/ECR/Bedrock 액세스/배포)는 이 repo 범위 밖. 로컬 docker-compose + LiteLLM 연동만 포함.
