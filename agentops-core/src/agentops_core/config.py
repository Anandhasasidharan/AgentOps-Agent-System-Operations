from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentOpsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/agentops"
    api_key: str = "dev-api-key"
    log_level: str = "info"
