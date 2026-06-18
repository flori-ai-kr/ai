"""마케팅 생성 오케스트레이션 — 채널 전략 선택 → LLM(구조화+폴백) → 후처리.

구조화 출력(``with_structured_output``)으로 스키마를 강제하고, 미지원/실패 시
견고한 JSON 파서로 폴백한다(vision.py와 동일 패턴).
"""

import json
import logging

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from app.agents.marketing.channels import get_channel
from app.agents.marketing.schemas import BlogDraft, BlogGenInput
from app.observability.tracing import observe

_log = logging.getLogger(__name__)


class MarketingGenerationError(Exception):
    """LLM에서 구조화된 마케팅 초안을 생성하지 못함."""


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


async def _try_structured(model: BaseChatModel, messages: list, schema: type[BaseModel]) -> BaseModel | None:
    factory = getattr(model, "with_structured_output", None)
    if factory is None:
        return None
    try:
        structured = factory(schema)
        result = await structured.ainvoke(messages)
    except Exception:
        _log.debug("structured marketing generation unavailable, falling back", exc_info=True)
        return None
    if isinstance(result, schema):
        return result
    if isinstance(result, dict):
        try:
            return schema(**result)
        except (ValidationError, TypeError):
            return None
    return None


@observe(name="generate_marketing_content")
async def generate(model: BaseChatModel, channel_name: str, gen_input: BlogGenInput) -> BaseModel:
    """채널 이름으로 디스패치해 마케팅 초안을 생성한다."""
    try:
        channel = get_channel(channel_name)
    except KeyError as exc:
        raise MarketingGenerationError(str(exc)) from exc

    schema = channel.output_schema()
    messages = channel.build_messages(gen_input)

    draft = await _try_structured(model, messages, schema)
    if draft is None:
        ai = await model.ainvoke(messages)
        raw = ai.content if isinstance(ai.content, str) else str(ai.content)
        try:
            draft = schema(**_extract_json(raw))
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            raise MarketingGenerationError("could not generate marketing draft") from exc

    return channel.postprocess(draft, gen_input)


async def generate_blog_draft(model: BaseChatModel, gen_input: BlogGenInput) -> BlogDraft:
    """블로그 채널 편의 래퍼 — BlogDraft를 반환한다."""
    draft = await generate(model, "blog", gen_input)
    assert isinstance(draft, BlogDraft)
    return draft
