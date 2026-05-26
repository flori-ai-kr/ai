# flori-ai

Flori AI — paste a KakaoTalk screenshot, get a booking. FastAPI + LangGraph AI service for the Flori florist SaaS: it explains "why did sales drop this month?", turns chat screenshots into reservations, and books by voice.

An AI assistant for the busy solo florist. It holds **no direct database access** — instead it's a thin orchestration layer that calls the existing Spring REST API (`flori-ai/server`) as LangGraph tools. Multi-tenancy and subscription gating are enforced by Spring: the user's JWT is passed straight through on every backend call.

LLM and Vision run through a single multimodal model — **LiteLLM proxy → AWS Bedrock Claude Haiku 4.5**.

Docs:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — as-built architecture: topology, endpoints, layers, security model, tech stack (Korean)
- [docs/features/](docs/features/README.md) — per-feature architecture & flow: A(data analysis) · B(OCR→reservation) · C(voice) · D(agent) (Korean)
- [docs/DESIGN.md](docs/DESIGN.md) — design decisions, security model, tool catalog, conversation session (SSOT, Korean)
- [ROADMAP.md](ROADMAP.md) — SPEC list, order, status (Korean)
- [HANDOFF.md](HANDOFF.md) — last session state, next steps (Korean)
- [CLAUDE.md](CLAUDE.md) — autonomous execution protocol, stack, security checklist (Korean)

## Features (sequencing)

| Stage | Feature | Description |
|-------|---------|-------------|
| **A** | Data analytics | Reads stats APIs and lets the LLM explain sales/reservation trends (read-only) |
| **B** | OCR → reservation | KakaoTalk screenshot → vision LLM extraction → confirmation card → reservation |
| **C** | Voice | Voice command → STT → agent → voice reply (C1 push-to-talk → C2 realtime) |
| **D** | Agent | Multi-step, proactive agent composing the A/B/C tools |

## Responsibility split

| Layer | Responsibility |
|-------|----------------|
| **flori-ai/ai (this project)** | AI orchestration — tool-call loop, vision OCR, voice session, confirmation cards, usage caps, audit logging |
| flori-ai/server (`hazel-server`) | Spring REST API. Source of truth for data, multi-tenancy & subscription gating, `user_id` isolation. The verified surface the AI tools wrap |
| flori-ai/mobile | React Native app. JWT issuer, confirmation-card UI, voice I/O |
| LiteLLM → Bedrock | Claude Haiku 4.5 (text + Vision). Single entry point via the proxy |

## Tech stack

| Area | Tech |
|------|------|
| Framework | FastAPI + uvicorn |
| Agent | LangGraph (StateGraph / ReAct) |
| LLM & Vision | LiteLLM proxy → Bedrock Claude Haiku 4.5 |
| Schema | Pydantic v2 |
| HTTP | httpx (async) |
| Session & cache | Redis |
| Tracing | Langfuse (optional, v1) |
| Package manager | uv |
| Lint & test | ruff / pytest |

## Development (from SPEC-AI-001 onward)

```bash
uv sync                                              # install dependencies
uv run uvicorn app.main:app --reload --port 8000     # run locally
uv run ruff check . && uv run ruff format .          # lint + format
uv run pytest                                        # tests
docker compose up -d                                 # local stack (ai-server + redis)
```

## Authentication

The AI server never issues or signature-verifies a JWT. The client (app) obtains a user JWT from the backend and passes it to the AI server, which **forwards it as-is** on backend REST calls. Isolation and gating are guaranteed by Spring. See [docs/DESIGN.md](docs/DESIGN.md) §5 (Security model).

> Infrastructure (EC2/ECR/Bedrock model access/deployment) is out of scope for this repo — handled separately. Only the local docker-compose and LiteLLM wiring are included.
