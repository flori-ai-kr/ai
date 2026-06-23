"""LiteLLM 프록시 경유 LLM 클라이언트 팩토리.

모든 LLM·Vision 호출은 LiteLLM(OpenAI 호환) 프록시를 거친다. 모델명은 LiteLLM에
등록된 ``claude-haiku-4-5`` (→ Bedrock Claude Haiku 4.5). 실제 호출은 기능 SPEC에서.
"""

from langchain_openai import ChatOpenAI

from app.core.config import Settings


def build_chat_model(settings: Settings, *, model: str | None = None, temperature: float = 0.0) -> ChatOpenAI:
    """설정으로 ChatOpenAI를 구성한다(구성만, 네트워크 호출 없음).

    ``model`` 미지정 시 ``settings.llm_model``을 쓴다. 마케팅 등 특정 경로가
    다른 모델/temperature를 쓰고 싶으면 인자로 넘긴다.
    """
    return ChatOpenAI(
        model=model or settings.llm_model,
        base_url=settings.litellm_base_url,
        # 로컬/테스트에서 LiteLLM master key 미설정 시에도 구성은 성공해야 한다.
        # ("sk-" 접두사를 피해 시크릿 스캐너 오탐 방지)
        api_key=settings.litellm_api_key or "local-noop",
        temperature=temperature,
    )


def build_marketing_chat_model(settings: Settings) -> ChatOpenAI:
    """마케팅(블로그) 전용 모델. 말투 모방 품질을 위해 강한 모델 + 높은 temperature."""
    return build_chat_model(
        settings,
        model=settings.marketing_model or settings.llm_model,
        temperature=settings.marketing_temperature,
    )
