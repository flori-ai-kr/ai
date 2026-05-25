"""환경 변수 기반 설정. 평문 시크릿은 코드에 두지 않고 env로만 주입."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """필드명이 곧 환경변수명(대소문자 무시). 예: ``llm_model`` ← ``LLM_MODEL``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (LiteLLM 프록시 경유)
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"

    # 백엔드 (Spring REST — 도구 대상)
    backend_base_url: str = "http://localhost:8080"

    # Redis (세션·캡)
    redis_url: str = "redis://localhost:6379/0"

    # 인증 / 캡 / 타임아웃 / 세션
    me_cache_ttl_seconds: int = 60
    request_timeout_seconds: float = 30.0
    usage_cap_per_day: int = 500
    session_ttl_seconds: int = 86400
    pending_ttl_seconds: int = 600  # 쓰기 제안(확인 카드) 유효시간

    # 음성 (C — AWS Transcribe/Polly)
    aws_region: str = "ap-northeast-2"
    polly_voice: str = "Seoyeon"  # 한국어 음성
    transcribe_language: str = "ko-KR"

    # 관측성 (D — Langfuse, v1 선택. 미설정 시 no-op)
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = ""


@lru_cache
def get_settings() -> Settings:
    """프로세스 단위 싱글톤 설정."""
    return Settings()
