from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["anthropic", "fake"] = "anthropic"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    workflow_recursion_limit: int = 10
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 10_485_760
    database_url: str = "sqlite:///./data/eduvision.db"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
