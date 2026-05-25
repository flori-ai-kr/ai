from app.core.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.llm_model == "claude-haiku-4-5"
    assert s.litellm_base_url.startswith("http")
    assert s.backend_base_url.startswith("http")
    assert s.redis_url.startswith("redis://")
    assert s.me_cache_ttl_seconds == 60
    assert s.request_timeout_seconds > 0
    assert s.usage_cap_per_day > 0


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "some-other-model")
    monkeypatch.setenv("BACKEND_BASE_URL", "https://backend.example.com")
    monkeypatch.setenv("ME_CACHE_TTL_SECONDS", "120")
    s = Settings()
    assert s.llm_model == "some-other-model"
    assert s.backend_base_url == "https://backend.example.com"
    assert s.me_cache_ttl_seconds == 120
