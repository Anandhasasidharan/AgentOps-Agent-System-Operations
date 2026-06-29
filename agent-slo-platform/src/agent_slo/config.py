"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/agent_slo"
    api_key: str = "dev-api-key"
    log_level: str = "info"
    otel_receiver_path: str = "/v1/traces"
    default_burn_rate_thresholds: list[float] = [0.02, 0.05, 0.10]

    class Config:
        env_prefix = ""
        case_sensitive = False
