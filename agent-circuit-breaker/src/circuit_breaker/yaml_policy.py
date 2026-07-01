"""YAML policy specification parser."""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Condition(BaseModel):
    model_config = ConfigDict(extra="allow")

    match_tool: str | None = Field(default=None, alias="matchTool")
    tools: list[str] | None = None
    max_calls: int | None = Field(default=None, alias="maxCalls")
    max_tokens: int | None = Field(default=None, alias="maxTokens")
    max_risk_score: float | None = Field(default=None, alias="maxRiskScore")
    max_anomaly_score: float | None = Field(default=None, alias="maxAnomalyScore")
    max_consecutive_same_tool: int | None = Field(default=None, alias="maxConsecutiveSameTool")
    start: float | None = None
    end: float | None = None


class PolicyAction(BaseModel):
    action: str = Field(default="block", pattern=r"^(allow|block|reroute|kill|alert)$")
    config: dict[str, Any] | None = None


class PolicySpec(BaseModel):
    policy_type: str = Field(
        ...,
        alias="type",
        pattern=r"^(tool_allowlist|tool_blocklist|rate_limit|token_budget|risk_threshold|anomaly_threshold|time_window|reasoning_loop)$",
    )
    priority: int = 0
    enabled: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    action: PolicyAction = Field(default_factory=lambda: PolicyAction(action="block"))


class PolicyYaml(BaseModel):
    api_version: str = Field(..., alias="apiVersion")
    kind: str = Field(default="Policy", pattern=r"^(Policy)$")
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec: PolicySpec


def parse_yaml(content: str) -> list[PolicyYaml]:
    documents = list(yaml.safe_load_all(content))
    return [PolicyYaml(**doc) for doc in documents if doc]
