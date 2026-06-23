from app.agents.marketing.geo_rules import BANNED_BACKREFS, BANNED_DEMONSTRATIVES
from app.agents.marketing.postprocess import postprocess_blog, strip_demonstratives
from app.agents.marketing.schemas import BlogDraft, BlogFaq, BlogSection


def test_strip_replaces_demonstratives_with_shop_name():
    out = strip_demonstratives("이 가게에서 산 장미가 좋아요", "플로리 플라워")
    assert "이 가게" not in out
    assert "플로리 플라워" in out


def test_strip_uses_default_when_no_shop_name():
    out = strip_demonstratives("본 매장 추천 상품입니다", None)
    assert "본 매장" not in out
    assert out.strip() != ""


def test_strip_removes_backreferences():
    out = strip_demonstratives("앞서 말한 장미는 인기상품", "플로리")
    assert "앞서 말한" not in out
    assert "장미는 인기상품" in out


def test_postprocess_blog_clears_all_banned_in_every_field():
    draft = BlogDraft(
        title="이곳 베스트 꽃다발",
        sections=[BlogSection(heading="앞서 본 추천", body="이 가게 장미가 최고")],
        faq=[BlogFaq(q="이 매장 영업시간?", a="우리 가게는 10시 오픈")],
        hashtags=["#꽃다발"],
    )
    out = postprocess_blog(draft, shop_name="플로리")
    blob = " ".join([out.title] + [s.heading + s.body for s in out.sections] + [f.q + f.a for f in out.faq])
    for banned in BANNED_DEMONSTRATIVES:
        assert banned not in blob
    for backref in BANNED_BACKREFS:
        assert backref not in blob
    assert out.hashtags == ["#꽃다발"]
