"""결정적 후처리 — LLM 출력에서 GEO 위반(지시대명사)을 제거한다.

인수기준: 후처리 후 본문에 금지 지시대명사가 남지 않는다.
"""

from app.agents.marketing.geo_rules import BANNED_BACKREFS, BANNED_DEMONSTRATIVES
from app.agents.marketing.schemas import BlogDraft, BlogFaq, BlogSection

_DEFAULT_SHOP = "저희 꽃집"


def strip_demonstratives(text: str, shop_name: str | None) -> str:
    """금지 지시대명사를 상호(없으면 기본어)로 치환하고 백레퍼런스 표현을 제거한다."""
    if not text:
        return text
    replacement = (shop_name or "").strip() or _DEFAULT_SHOP
    for demo in BANNED_DEMONSTRATIVES:
        text = text.replace(demo, replacement)
    for backref in BANNED_BACKREFS:
        text = text.replace(backref, "")
    return text


def postprocess_blog(draft: BlogDraft, shop_name: str | None) -> BlogDraft:
    """초안 전 텍스트 필드에 지시대명사 치환을 적용한 새 BlogDraft를 반환한다."""

    def fix(t: str) -> str:
        return strip_demonstratives(t, shop_name)

    return BlogDraft(
        title=fix(draft.title),
        sections=[BlogSection(heading=fix(s.heading), body=fix(s.body)) for s in draft.sections],
        faq=[BlogFaq(q=fix(f.q), a=fix(f.a)) for f in draft.faq],
        hashtags=list(draft.hashtags),
    )
