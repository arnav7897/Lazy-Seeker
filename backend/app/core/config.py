from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./lazyseeker.db"
    secret_key: str = "lazy-seeker-local-dev-secret-key"
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    environment: str = "development"
    access_token_expire_days: int = 7


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
