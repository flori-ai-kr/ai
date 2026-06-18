"""네이버 블로그 채널 — GEO 규칙 + 말투 few-shot + 매장맥락 + 사진(vision)."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.marketing.geo_rules import BLOG_SYSTEM, GEO_RULES, OUTPUT_SPEC
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
    if ctx.avg_order_value:
        lines.append(f"- 평균 객단가: {ctx.avg_order_value:,}원")
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
        instruction_parts = [
            "다음 조건으로 네이버 블로그 초안을 작성하세요.",
            GEO_RULES,
            "",
            "[타깃 검색 키워드]\n" + fence_user_input(gen_input.keyword),
        ]
        if gen_input.situation:
            instruction_parts.append("[상황/시즌]\n" + fence_user_input(gen_input.situation))
        if gen_input.memo:
            instruction_parts.append("[사장님 메모]\n" + fence_user_input(gen_input.memo))

        store_block = _store_context_block(gen_input.store_context)
        if store_block:
            instruction_parts.append(store_block)

        for i, sample in enumerate(gen_input.tone_samples[:_MAX_TONE_SAMPLES], start=1):
            instruction_parts.append(f"[말투 샘플 {i} — 이 문체/어조를 모방]\n" + fence_user_input(sample))

        instruction_parts.append(OUTPUT_SPEC)

        content: list = [{"type": "text", "text": "\n\n".join(instruction_parts)}]
        for url in gen_input.photo_urls[:_MAX_PHOTOS]:
            content.append({"type": "image_url", "image_url": {"url": url}})

        return [SystemMessage(content=BLOG_SYSTEM), HumanMessage(content=content)]

    def postprocess(self, draft: BaseModel, gen_input: BlogGenInput) -> BaseModel:
        assert isinstance(draft, BlogDraft)
        shop_name = gen_input.store_context.shop_name if gen_input.store_context else None
        return postprocess_blog(draft, shop_name)
