"""SPEC-AI-008 — 마케팅 prompt_override seam 회귀 테스트."""

from app.agents.marketing.channels.blog import BlogChannel
from app.agents.marketing.schemas import BlogGenInput, PromptOverride


def test_blog_gen_input_accepts_prompt_override():
    gi = BlogGenInput(
        keyword="장미",
        prompt_override=PromptOverride(system_md="커스텀 시스템", temperature=0.5),
    )
    assert gi.prompt_override.system_md == "커스텀 시스템"
    assert gi.prompt_override.rules_md is None
    assert gi.prompt_override.temperature == 0.5


def test_blog_gen_input_default_no_override():
    gi = BlogGenInput(keyword="장미")
    assert gi.prompt_override is None


def test_override_replaces_only_provided_parts():
    ch = BlogChannel()
    gi = BlogGenInput(keyword="장미", prompt_override=PromptOverride(system_md="<<CUSTOM SYS>>"))
    msgs = ch.build_messages(gi)
    blob = str(msgs)
    assert "<<CUSTOM SYS>>" in blob  # system은 교체됨
    assert "네이버 GEO 구조 규칙" in blob  # rules는 기본값 유지(폴백)


def test_no_override_uses_defaults():
    ch = BlogChannel()
    msgs = ch.build_messages(BlogGenInput(keyword="장미"))
    blob = str(msgs)
    assert "꽃집 사장님" in blob  # 기본 BLOG_SYSTEM
