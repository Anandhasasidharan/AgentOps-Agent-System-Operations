"""Application configuration."""

from agentops_core.config import AgentOpsSettings


class Settings(AgentOpsSettings):
    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/circuit_breaker"
    kill_switch_ttl_seconds: int = 3600
    otel_exporter_endpoint: str = "http://localhost:8000/v1/traces"
    nats_url: str = ""
