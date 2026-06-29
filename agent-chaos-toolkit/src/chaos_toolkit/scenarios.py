"""Failure Scenario Engine — defines and resolves chaos experiment scenarios."""

from __future__ import annotations

import uuid
from typing import Any

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.models import Scenario


# ─── YAML Scenario Definition ──────────────────────────────────────────────────


class ScenarioMetadata(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class ScenarioSpec(BaseModel):
    target: str  # llm, tool, rag, mcp
    failure_mode: str
    config: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str = "graceful_degradation"
    agent_should_survive: bool = True


class ScenarioYaml(BaseModel):
    api_version: str = Field(default="chaosops.io/v1", alias="apiVersion")
    kind: str = Field(default="ChaosScenario")
    metadata: ScenarioMetadata
    spec: ScenarioSpec


def parse_scenario_yaml(content: str) -> list[ScenarioYaml]:
    documents = list(yaml.safe_load_all(content))
    return [ScenarioYaml(**doc) for doc in documents if doc]


# ─── Built-in Scenarios ────────────────────────────────────────────────────────


BUILTIN_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "llm-timeout",
        "description": "LLM takes too long to respond (>30s)",
        "target_type": "llm",
        "failure_mode": "timeout",
        "config": {"params": {"delay_seconds": 35}},
        "expected_behavior": "graceful_degradation",
        "agent_should_survive": True,
    },
    {
        "name": "llm-hallucination",
        "description": "LLM returns hallucinated information",
        "target_type": "llm",
        "failure_mode": "hallucination",
        "config": {"params": {}},
        "expected_behavior": "error_handled",
        "agent_should_survive": True,
    },
    {
        "name": "llm-refusal",
        "description": "LLM refuses to answer",
        "target_type": "llm",
        "failure_mode": "refusal",
        "config": {"params": {}},
        "expected_behavior": "fallback_used",
        "agent_should_survive": True,
    },
    {
        "name": "llm-model-downgrade",
        "description": "LLM model suddenly downgraded to weaker model",
        "target_type": "llm",
        "failure_mode": "model_downgrade",
        "config": {"params": {"downgraded_model": "gpt-3.5-turbo"}},
        "expected_behavior": "graceful_degradation",
        "agent_should_survive": True,
    },
    {
        "name": "tool-timeout",
        "description": "Tool call hangs indefinitely",
        "target_type": "tool",
        "failure_mode": "timeout",
        "config": {"params": {"delay_seconds": 30}},
        "expected_behavior": "retry_success",
        "agent_should_survive": True,
    },
    {
        "name": "tool-crash",
        "description": "Tool returns 500 internal error",
        "target_type": "tool",
        "failure_mode": "crash",
        "config": {"params": {}},
        "expected_behavior": "error_handled",
        "agent_should_survive": True,
    },
    {
        "name": "tool-bad-output",
        "description": "Tool returns malformed output",
        "target_type": "tool",
        "failure_mode": "bad_output",
        "config": {"params": {}},
        "expected_behavior": "error_handled",
        "agent_should_survive": True,
    },
    {
        "name": "tool-wrong-data",
        "description": "Tool returns incorrect/empty data",
        "target_type": "tool",
        "failure_mode": "wrong_data",
        "config": {"params": {}},
        "expected_behavior": "fallback_used",
        "agent_should_survive": True,
    },
    {
        "name": "rag-no-results",
        "description": "RAG retrieval returns empty results",
        "target_type": "rag",
        "failure_mode": "no_results",
        "config": {"params": {}},
        "expected_behavior": "graceful_degradation",
        "agent_should_survive": True,
    },
    {
        "name": "rag-bad-data",
        "description": "RAG returns irrelevant context",
        "target_type": "rag",
        "failure_mode": "bad_data",
        "config": {"params": {}},
        "expected_behavior": "error_handled",
        "agent_should_survive": True,
    },
    {
        "name": "rag-corrupted-context",
        "description": "RAG returns corrupted/unparseable context",
        "target_type": "rag",
        "failure_mode": "corrupted_context",
        "config": {"params": {}},
        "expected_behavior": "error_handled",
        "agent_should_survive": True,
    },
    {
        "name": "rag-slow-response",
        "description": "RAG retrieval is extremely slow",
        "target_type": "rag",
        "failure_mode": "slow_response",
        "config": {"params": {"delay_seconds": 20}},
        "expected_behavior": "graceful_degradation",
        "agent_should_survive": True,
    },
    {
        "name": "mcp-server-down",
        "description": "MCP server is unreachable",
        "target_type": "mcp",
        "failure_mode": "server_down",
        "config": {"params": {}},
        "expected_behavior": "fail_fast",
        "agent_should_survive": True,
    },
    {
        "name": "mcp-timeout",
        "description": "MCP request times out",
        "target_type": "mcp",
        "failure_mode": "timeout",
        "config": {"params": {"delay_seconds": 35}},
        "expected_behavior": "retry_success",
        "agent_should_survive": True,
    },
    {
        "name": "mcp-auth-failure",
        "description": "MCP authentication fails",
        "target_type": "mcp",
        "failure_mode": "auth_failure",
        "config": {"params": {}},
        "expected_behavior": "fail_fast",
        "agent_should_survive": True,
    },
]


async def seed_builtin_scenarios(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[Scenario]:
    existing = await session.execute(
        select(Scenario).where(Scenario.tenant_id == tenant_id)
    )
    existing_names = {s.name for s in existing.scalars().all()}

    created: list[Scenario] = []
    for spec in BUILTIN_SCENARIOS:
        if spec["name"] not in existing_names:
            scenario = Scenario(
                tenant_id=tenant_id,
                **{k: spec[k] for k in spec},
            )
            session.add(scenario)
            created.append(scenario)

    if created:
        await session.flush()
    return created
