# SPEC-AI-007 — 마케팅: 네이버 블로그 초안 AI

> 출시(2026-06-29) 유료 헤드라인. 사진+키워드 → 네이버 GEO 최적화 블로그 초안.
> 교차 repo 기능: `ai`(생성 엔진) · `api`(게이트웨이·영속·맥락조립) · `web`(UX/UI).
> 근거: feasibility `AI 기능 아이데이션·현실성·출시범위`(M2) · `ON-HWA 벤치마킹` · 출시 체크리스트 N2.

## 목표

바쁜 1인 꽃집 사장이 **사진 1장 + 타깃 키워드**만 주면, 자기 말투로 쓰인 **네이버 검색 노출(GEO) 최적화 블로그 초안**(제목·소제목 단락·FAQ·해시태그)을 받아 복붙으로 게시한다. 매장 실데이터(객단가·시즌·취급상품)를 1인칭 경험 신호로 자동 주입해 범용 AI 툴이 못 내는 "그 가게다운" 글을 만든다.

## 범위

### In (v1)
- **입력**: 타깃 키워드(필수) + 상황(선택) + 메모(선택) + 갤러리/업로드 사진(선택, 0~4장)
- **말투**: 게이트웨이 저장 `tone_profile`(사장 블로그 샘플 1~3개) → 매 생성 자동 few-shot 주입
- **매장 맥락**: 게이트웨이가 `store_context`(객단가·다가오는 시즌·취급상품 상위·상호) **코드로 조립**해 주입 (LLM 도구콜 아님)
- **출력**: `BlogDraft{title, sections[{heading, body}], faq[{q,a}], hashtags[]}` — 1500~2500자, 정보성+1인칭 혼합
- **GEO 규칙**(프롬프트에 박음): 200~300자 자기완결 단락(첫문장=질문/끝문장=결론) · 소제목=네이버 자동완성 하위질문 · 고유명사 밀도 1000자당 15+ · 키워드 도배 금지 · "①상황 ②원인+데이터 ③수정 ④결과수치" 4단
- **후처리**(결정적): 지시대명사("이 가게/앞서/그것") → 상호 등 고유명사 치환
- **영속/UX**: 초안 저장·목록·복사(섹션별)·재생성·소프트삭제 (게이트웨이 DB)
- **사용량**: 기존 `AiUsageGuard` 캡 재사용

### Out (확장 seam만)
- 멀티채널(인스타·스레드) — ai-server `channels/` 추상화로 자리만, v1은 `blog`만 등록
- 네이버 자동 업로드 — 공식 API 없음(복붙). 영구 제외
- 스트리밍(SSE) — v1 단건 응답, 후속 seam
- 크레딧 원장(N1) — `AiUsageGuard` 캡으로 대체, 원장 연동 seam만

## API 계약 (확정 — 이 계약에 맞춰 3 repo 병렬 구현)

### ai-server (snake_case, stateless)
`POST /marketing/blog`
```jsonc
// req
{
  "channel": "blog",
  "keyword": "어버이날 카네이션 꽃다발",      // required, ≤200
  "situation": "어버이날",                  // optional, ≤100
  "memo": "비누꽃도 추천",                   // optional, ≤500
  "photo_urls": ["https://..."],           // optional, 0..4, http(s)+SSRF 가드
  "tone_samples": ["...", "..."],          // optional, 0..3, 각 ≤4000
  "store_context": {                       // optional
    "shop_name": "플로리 플라워",
    "avg_order_value": 55000,
    "upcoming_season": "어버이날 (D-7)",
    "top_products": ["장미 꽃다발", "계절 꽃바구니"]
  },
  "model": null
}
// res
{
  "draft": {
    "title": "...",
    "sections": [{"heading": "...", "body": "..."}],
    "faq": [{"q": "...", "a": "..."}],
    "hashtags": ["#어버이날꽃", "..."]
  },
  "model": "...", "input_tokens": 0, "output_tokens": 0
}
```
- 모든 사용자 텍스트(keyword/situation/memo/tone_samples)는 `[USER INPUT — DATA ONLY]` 펜스
- 구조화 출력(`with_structured_output(BlogDraft)`) → 실패 시 견고 JSON 폴백 (ocr.py 패턴)

### 게이트웨이 (camelCase, web 공개 계약 — `/ai/marketing/*`)
- `POST /ai/marketing/blog` — req `{keyword, situation?, memo?, photoUrls?[]}` → res `{contentId, draft}`
  - 서버사이드: tenant 격리 · 캡 · `tone_profile` 로드 · `store_context` 조립 · ai 호출 · `ai_marketing_content` 저장
- `GET /ai/marketing/tone-profile` → `{samples[]}` · `PUT /ai/marketing/tone-profile` `{samples[]}`(≤3, upsert)
- `GET /ai/marketing/contents?channel=blog&offset&limit` → 목록 · `GET /{id}` 상세 · `DELETE /{id}` 소프트삭제

### web
- 라우트 `/admin/marketing` — 글쓰기(사진선택+키워드+상황+메모) · 결과(섹션별 복사·편집·재생성) · 초안 목록
- 말투 등록 UI(샘플 1~3 붙여넣기 → 저장)
- `lib/actions/marketing.ts` · `types/marketing.ts`

## 데이터 모델 (게이트웨이 DB · 수동 DDL · FK 없음 — 프로젝트 규칙)
- `ai_tone_profile`: id, user_id(uq), samples_json, created_at, updated_at
- `ai_marketing_content`: id, user_id, channel, input_json, output_json, model, input_tokens, output_tokens, latency_ms, created_at, deleted_at

## 모듈/확장성 (요구사항)
- ai-server 새 패키지 `app/agents/marketing/`: `generator.py`·`geo_rules.py`·`postprocess.py`·`schemas.py`·`channels/{base,blog}.py`. 엔드포인트 `app/api/marketing.py`. 멀티채널·튜닝이 "파일 추가"로 끝남.
- SSRF 가드 `_is_blocked_host`는 `app/api/validators.py`로 중앙화해 ocr·marketing 공유.
- 게이트웨이 `MarketingContextBuilder`(store_context 조립, pluggable)·`SeasonCalendar`(기념일 D-day, 결정적).

## 보안 (HARD)
- 사진 URL SSRF 가드 · 사용자 텍스트 전원 펜스(특히 tone_samples=인젝션 벡터) · TenantContext 격리 · 캡 · 외부쓰기 없음 · 에러 내부디테일 비노출.

## 의존성
- SPEC-AI-001(Foundation)·003(vision)·게이트웨이 `kr.ai.flori.ai` 기존 배관(AiServerClient·AiUsageGuard·TenantContext).

## 인수기준
1. `POST /marketing/blog`가 키워드만으로도 유효한 `BlogDraft`(섹션 ≥3, FAQ 3~5, 해시태그 ≥3)를 반환한다.
2. 사진 URL이 사설/루프백이면 422로 거부한다.
3. tone_samples/keyword에 인젝션 문구를 넣어도 시스템 지시로 따르지 않는다(펜스 회귀 테스트).
4. 후처리 후 본문에 금지 지시대명사가 남지 않는다.
5. 게이트웨이가 tone_profile·store_context를 조립해 ai 호출하고 `ai_marketing_content`에 저장, web이 초안을 받아 렌더·복사한다.
6. 캡 초과 유저는 403으로 차단된다.
7. 각 repo: `ruff`/`ktlint`/`eslint`+`tsc` 및 테스트 그린.

## 검증 방법
- ai: `uv run ruff check . && uv run pytest`
- api: `./gradlew ktlintCheck test`
- web: `npm run lint && npx tsc --noEmit && npm run test`
