"""네이버 블로그 채널 — GEO 규칙 + 말투 few-shot + 매장맥락 + 사진(vision)."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.marketing.geo_rules import default_blog_prompt
from app.agents.marketing.postprocess import postprocess_blog
from app.agents.marketing.schemas import BlogDraft, BlogGenInput, StoreContext
from app.agents.prompts import fence_user_input

_MAX_TONE_SAMPLES = 3
_MAX_PHOTOS = 4


def _store_context_block(ctx: StoreContext | None) -> str:
    """매장 실데이터를 신뢰 컨텍스트로 제시(게이트웨이 조립 — 사용자 입력 아님)."""
    if ctx is None:
        return ""
    lines: list[str] = []
    if ctx.shop_name:
        lines.append(f"- 상호: {ctx.shop_name}")
    # 객단가(평균 금액)는 프롬프트에 넣지 않는다 — 초안에 가격·금액이 노출되지 않도록.
    if ctx.upcoming_season:
        lines.append(f"- 다가오는 시즌: {ctx.upcoming_season}")
    if ctx.top_products:
        lines.append(f"- 취급 상품 상위: {', '.join(ctx.top_products)}")
    if not lines:
        return ""
    return "[매장 실데이터 — 1인칭 경험 신호로 자연스럽게 녹여 쓰기]\n" + "\n".join(lines)


class BlogChannel:
    name = "blog"

    def output_schema(self) -> type[BaseModel]:
        return BlogDraft

    def build_messages(self, gen_input: BlogGenInput) -> list:
        # 정적 프롬프트 3조각: override 있는 것만 교체, 나머지는 geo_rules 기본값 폴백.
        base = default_blog_prompt()
        ov = gen_input.prompt_override
        system_md = ov.system_md if ov and ov.system_md else base["system_md"]
        rules_md = ov.rules_md if ov and ov.rules_md else base["rules_md"]
        output_spec_md = ov.output_spec_md if ov and ov.output_spec_md else base["output_spec_md"]

        instruction_parts = ["다음 조건으로 네이버 블로그 초안을 작성하세요."]

        # 말투 샘플을 GEO 규칙보다 '먼저' + 강조해 제시한다 — 문체 모방이 핵심이라
        # 구조 규칙(GEO)에 톤이 눌리지 않도록 우선순위를 프롬프트 위치로도 못박는다.
        samples = gen_input.tone_samples[:_MAX_TONE_SAMPLES]
        if samples:
            instruction_parts.append(
                "[★ 최우선 — 사장님 말투 모방]\n"
                "아래 글들은 사장님이 직접 쓴 블로그입니다. 이 문체(이모지 빈도·문장 길이·말끝 어미·"
                "감탄 표현·고유명사와 해시태그를 본문에 녹이는 방식)를 그대로 모방해서 쓰세요. "
                "표준 정보글 문체로 평탄화하지 마세요."
            )
            for i, sample in enumerate(samples, start=1):
                instruction_parts.append(f"[말투 샘플 {i}]\n" + fence_user_input(sample))

        instruction_parts.append(rules_md)
        instruction_parts.append("[타깃 검색 키워드]\n" + fence_user_input(gen_input.keyword))
        if gen_input.situation:
            instruction_parts.append("[상황/시즌]\n" + fence_user_input(gen_input.situation))
        if gen_input.memo:
            instruction_parts.append("[사장님 메모]\n" + fence_user_input(gen_input.memo))

        store_block = _store_context_block(gen_input.store_context)
        if store_block:
            instruction_parts.append(store_block)

        instruction_parts.append(output_spec_md)

        content: list = [{"type": "text", "text": "\n\n".join(instruction_parts)}]
        for url in gen_input.photo_urls[:_MAX_PHOTOS]:
            content.append({"type": "image_url", "image_url": {"url": url}})

        return [SystemMessage(content=system_md), HumanMessage(content=content)]

    def postprocess(self, draft: BaseModel, gen_input: BlogGenInput) -> BaseModel:
        if not isinstance(draft, BlogDraft):
            raise TypeError(f"expected BlogDraft, got {type(draft).__name__}")
        shop_name = gen_input.store_context.shop_name if gen_input.store_context else None
        return postprocess_blog(draft, shop_name)
