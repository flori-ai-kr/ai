from app.agents.llm_client import build_chat_model
from app.core.config import Settings


def test_build_chat_model_uses_settings(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.local:4000")
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-test")
    settings = Settings()

    model = build_chat_model(settings)

    assert model.model_name == "claude-haiku-4-5"
    assert str(model.openai_api_base) == "http://litellm.local:4000"


def test_build_chat_model_tolerates_empty_api_key():
    # LiteLLM master key 미설정(로컬)에서도 구성은 성공해야 한다(네트워크 호출 없음).
    settings = Settings(litellm_api_key="")
    model = build_chat_model(settings)
    assert model.model_name == settings.llm_model
