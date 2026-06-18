# M — 마케팅: 네이버 블로그 초안 AI (`POST /marketing/blog`)

> SPEC-AI-007 · **출시 유료 헤드라인**. 교차 repo(ai 생성엔진 · api 영속/맥락조립 · web UX). 전체 그림: [../ARCHITECTURE.md](../ARCHITECTURE.md)

## 개요
사진(선택) + 타깃 검색키워드 → **네이버 검색 노출(GEO) 최적화 블로그 초안**(제목 · 소제목 단락 · 하단 FAQ · 해시태그)을 사장님 말투로 생성. 네이버에 **복붙**해 쓰는 용도(자동 업로드는 공식 API 없어 영구 제외). 매장 실데이터(객단가·시즌·취급상품)를 1인칭 경험 신호로 자동 주입해 범용 AI 툴이 못 내는 "그 가게다운" 글을 만든다.

## 사용 스택 · 모델 · AI 기법
| 영역 | 사용 |
|------|------|
| 생성 모델 | **Bedrock Claude Haiku 4.5 (멀티모달)** via LiteLLM — 사진+텍스트, A·B와 동일 모델 |
| 멀티모달 호출 | `HumanMessage(content=[{type:text}, {type:image_url}×N])` (vision.py 패턴 재사용) |
| 출력 강제 | `with_structured_output(BlogDraft)` → 실패 시 견고 JSON 폴백 (ocr.py와 동일) |
| **말투 학습** | **few-shot 프롬프트 주입** — 사장 블로그 샘플 1~3개를 프롬프트에 예시로 박음. **RAG·임베딩·파인튜닝 아님**(단일 가게 톤엔 few-shot이 더 단순·저렴) |
| **GEO 최적화** | 규칙셋(`geo_rules.py`)을 시스템/유저 프롬프트에 규칙으로 주입(자기완결 단락·하위질문 소제목·고유명사 밀도·키워드 도배 금지·4단 경험구조) |
| **매장 맥락 주입** | 게이트웨이가 **코드로 집계**(객단가·시즌·취급상품)해 `store_context`로 전달 — LLM 도구콜 아님(저비용·결정적) |
| 후처리 | `postprocess.py` 결정적 — 지시대명사("이 가게/이곳/앞서") → 상호 치환 |
| 채널 추상화 | `channels/`(Protocol) — v1 `blog`만 등록, 인스타·스레드는 파일 추가만으로 확장 |

> **RAG는 쓰지 않는다.** 말투는 few-shot(샘플 직접 주입), 매장 데이터는 게이트웨이 코드 집계. 벡터DB·검색·임베딩 없음 → 단일 LLM 호출 = 비용/지연 예측가능.

## 아키텍처 레이어 (ai-server)
| 레이어 | 파일 | 역할 |
|--------|------|------|
| 전송 | `app/api/marketing.py` | `POST /marketing/blog` — 입력검증(SSRF·길이) → 생성 → BlogDraft |
| 오케스트레이션 | `app/agents/marketing/generator.py` | 채널 디스패치 → LLM(구조화+폴백) → 후처리 |
| 채널 전략 | `app/agents/marketing/channels/{base,blog}.py` | 프롬프트·출력스키마·후처리 캡슐화 |
| GEO 규칙 | `app/agents/marketing/geo_rules.py` | 시스템 프롬프트 + GEO 규칙셋 + 출력 스펙(데이터로 분리) |
| 후처리 | `app/agents/marketing/postprocess.py` | 지시대명사 치환(결정적) |
| 스키마 | `app/agents/marketing/schemas.py` | `BlogGenInput`·`BlogDraft`·`StoreContext` |
| 공용 검증 | `app/api/validators.py` | `validate_http_image_url`(ocr·marketing SSRF 공용) |

## 엔드포인트 · 계약
### ai-server (내부망, snake_case, stateless)
| 엔드포인트 | 입력 | 출력 |
|-----------|------|------|
| `POST /marketing/blog` | `{channel, keyword, situation?, memo?, photo_urls[], tone_samples[], store_context?, model?}` | `{draft:{title,sections[{heading,body}],faq[{q,a}],hashtags[]}, model, input_tokens, output_tokens}` |

### 게이트웨이 (web 공개, camelCase, `/ai/marketing/*`)
| 엔드포인트 | 역할 |
|-----------|------|
| `POST /ai/marketing/blog` | tone_profile 로드 + store_context 조립 + ai 호출 + `ai_marketing_content` 저장 → `{contentId, draft}` |
| `GET·PUT /ai/marketing/tone-profile` | 말투 샘플(≤3) 조회/upsert |
| `GET /ai/marketing/contents`·`/{id}`·`DELETE /{id}` | 초안 목록/상세/소프트삭제 |

## 보안
- 사진 URL SSRF 가드(http(s)+비사설) · **사용자 텍스트 전원 `[USER INPUT — DATA ONLY]` 펜스**(특히 tone_samples=인젝션 벡터) · TenantContext 격리(게이트웨이) · `AiUsageGuard` 캡 · 외부 쓰기 없음 · 에러 내부디테일 비노출.

## 확장 seam (구현 안 함, 자리만)
- 멀티채널(인스타·스레드) = `channels/`에 전략 추가 + 레지스트리 등록
- 스트리밍(SSE) = 긴 출력 UX 후속
- 크레딧 원장(N1) = `AiUsageGuard` 캡 → 원장 차감으로 교체

## 테스트
ai: `test_marketing_{postprocess,generator,api}.py` (15) — 구조화/폴백·펜스·SSRF·후처리 불변식·키워드만 생성. `uv run ruff check . && uv run pytest` → **115 통과**.
