"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    database_url: str = "sqlite+aiosqlite:///chaos_toolkit.db"
    api_key: str = "dev-api-key"
    log_level: str = "info"
    default_llm_model: str = "gpt-4o"
