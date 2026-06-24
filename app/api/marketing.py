"""마케팅 초안 생성 엔드포인트 — 게이트웨이 뒤 stateless.

여기서는 저장하지 않는다. 초안만 돌려주고, 게이트웨이가 영속/목록/복사를 소유한다.
말투 샘플·매장 맥락은 게이트웨이가 조립해 보낸다(ai-server는 무상태).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, field_validator

from app.agents.llm_client import build_chat_model
from app.agents.marketing.generator import MarketingGenerationError, generate
from app.agents.marketing.schemas import BlogDraft, BlogGenInput, PromptOverride, StoreContext
from app.api.deps import get_marketing_chat_model, get_request_context, get_settings
from app.api.validators import validate_http_image_url
from app.backend.auth import RequestContext
from app.core.config import Settings

router = APIRouter()
_log = logging.getLogger("flori.marketing")

_MAX_TONE_SAMPLES = 3
_MAX_PHOTOS = 4


class StoreContextIn(BaseModel):
    shop_name: str | None = Field(None, max_length=100)
    avg_order_value: int | None = Field(None, ge=0)
    upcoming_season: str | None = Field(None, max_length=100)
    top_products: list[str] = Field(default_factory=list, max_length=10)


class PromptOverrideIn(BaseModel):
    """게이트웨이(어드민 인증 통과)만 보내는 DB active 프롬프트 오버라이드. 부분 적용."""

    system_md: str | None = Field(None, max_length=20000)
    rules_md: str | None = Field(None, max_length=20000)
    output_spec_md: str | None = Field(None, max_length=4000)
    model: str | None = Field(None, max_length=64)
    temperature: float | None = Field(None, ge=0.0, le=2.0)


class MarketingBlogRequest(BaseModel):
    channel: str = "blog"
    keyword: str = Field(..., min_length=1, max_length=200)
    situation: str | None = Field(None, max_length=100)
    memo: str | None = Field(None, max_length=500)
    photo_urls: list[str] = Field(default_factory=list, max_length=_MAX_PHOTOS)
    tone_samples: list[str] = Field(default_factory=list, max_length=_MAX_TONE_SAMPLES)
    store_context: StoreContextIn | None = None
    model: str | None = None  # 게이트웨이 힌트(현재는 ai-server 설정 모델 사용)
    prompt_override: PromptOverrideIn | None = None

    @field_validator("photo_urls")
    @classmethod
    def _no_ssrf(cls, urls: list[str]) -> list[str]:
        return [validate_http_image_url(u) for u in urls]

    @field_validator("tone_samples")
    @classmethod
    def _cap_samples(cls, samples: list[str]) -> list[str]:
        # 각 샘플 길이 상한(컨텍스트 폭발/비용 방어). 초과분은 자른다.
        return [s[:4000] for s in samples]


class MarketingBlogResponse(BaseModel):
    draft: BlogDraft
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@router.post("/marketing/blog", response_model=MarketingBlogResponse)
async def marketing_blog(
    req: MarketingBlogRequest,
    ctx: RequestContext = Depends(get_request_context),
    model: BaseChatModel = Depends(get_marketing_chat_model),
    settings: Settings = Depends(get_settings),
) -> MarketingBlogResponse:
    ov = req.prompt_override
    _log.info(
        "📥 블로그 생성 요청 수신 | 채널=%s · keyword=%r · 상황=%s · 메모=%s · 사진=%d장 · 말투샘플=%d개 · 매장맥락=%s",
        req.channel,
        req.keyword,
        "있음" if req.situation else "없음",
        "있음" if req.memo else "없음",
        len(req.photo_urls),
        len(req.tone_samples),
        "있음" if req.store_context else "없음",
    )
    if ov:
        replaced = [
            name
            for name, value in (("system", ov.system_md), ("rules", ov.rules_md), ("output_spec", ov.output_spec_md))
            if value
        ]
        _log.info(
            "🧩 prompt_override 적용 | DB본문 교체=%s · 모델=%s · temperature=%s",
            f"[{', '.join(replaced)}]" if replaced else "없음(모델/temp만)",
            ov.model or "기본",
            ov.temperature if ov.temperature is not None else "기본",
        )
    else:
        _log.info("🧩 prompt_override 없음 → ai 코드 기본 프롬프트(geo_rules.py) 폴백 사용")

    gen_input = BlogGenInput(
        keyword=req.keyword,
        situation=req.situation,
        memo=req.memo,
        tone_samples=req.tone_samples,
        store_context=StoreContext(**req.store_context.model_dump()) if req.store_context else None,
        photo_urls=req.photo_urls,
        prompt_override=PromptOverride(**ov.model_dump()) if ov else None,
    )

    # model/temperature override 시 요청 단위로 모델을 재빌드(없으면 주입된 마케팅 모델 사용).
    used_model = settings.marketing_model or settings.llm_model
    used_temp = settings.marketing_temperature
    if ov and (ov.model or ov.temperature is not None):
        used_model = ov.model or used_model
        used_temp = ov.temperature if ov.temperature is not None else settings.marketing_temperature
        model = build_chat_model(settings, model=used_model, temperature=used_temp)
    _log.info("🤖 생성 모델 확정 | model=%s · temperature=%s", used_model, used_temp)

    try:
        draft = await generate(model, req.channel, gen_input)
    except MarketingGenerationError:
        _log.warning("❌ 블로그 초안 생성 실패 — 구조화 출력/JSON 파싱 불가")
        raise HTTPException(status_code=422, detail="블로그 초안을 생성하지 못했어요.") from None

    if not isinstance(draft, BlogDraft):
        _log.warning("❌ 생성 결과 타입 오류 | got=%s", type(draft).__name__)
        raise HTTPException(status_code=500, detail="생성 오류")

    _log.info(
        "✅ 블로그 초안 생성 완료 | 제목=%r · 섹션=%d개 · FAQ=%d개 · 해시태그=%d개",
        draft.title,
        len(draft.sections),
        len(draft.faq),
        len(draft.hashtags),
    )
    return MarketingBlogResponse(draft=draft, model=used_model)
