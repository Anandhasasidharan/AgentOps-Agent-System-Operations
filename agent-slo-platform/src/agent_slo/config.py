"""Application configuration."""

from agentops_core.config import AgentOpsSettings


class Settings(AgentOpsSettings):
    database_url: str = "postgresql+asyncpg://agentops:agentops@localhost:5432/agent_slo"
    otel_receiver_path: str = "/v1/traces"
    default_burn_rate_thresholds: list[float] = [0.02, 0.05, 0.10]
