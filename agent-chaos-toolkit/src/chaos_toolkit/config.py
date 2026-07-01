"""Application configuration."""

from agentops_core.config import AgentOpsSettings


class Settings(AgentOpsSettings):
    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/chaos_toolkit"
    default_llm_model: str = "gpt-4o"
    otel_exporter_endpoint: str = "http://localhost:8000/v1/traces"
