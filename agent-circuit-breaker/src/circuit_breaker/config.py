"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/circuit_breaker"
    api_key: str = "dev-api-key"
    log_level: str = "info"
    kill_switch_ttl_seconds: int = 3600
