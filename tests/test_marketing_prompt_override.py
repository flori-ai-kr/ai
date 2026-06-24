"""SPEC-AI-008 — 마케팅 prompt_override seam 회귀 테스트."""

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
