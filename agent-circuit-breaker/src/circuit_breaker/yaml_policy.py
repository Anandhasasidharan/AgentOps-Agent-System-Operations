"""YAML policy specification parser.

The ``conditions`` field is validated with the same typed schemas as the HTTP
API (``circuit_breaker.policy_conditions``). That keeps ``cbctl apply`` and
``POST /api/v1/policies`` from accepting different policy shapes.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from circuit_breaker.policy_conditions import PolicyConditionsError, validate_conditions


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

    @model_validator(mode="after")
    def _validate_conditions(self) -> PolicySpec:
        try:
            self.conditions = validate_conditions(self.policy_type, self.conditions)
        except PolicyConditionsError as exc:
            raise ValueError(str(exc)) from exc
        return self


class PolicyYaml(BaseModel):
    api_version: str = Field(..., alias="apiVersion")
    kind: str = Field(default="Policy", pattern=r"^(Policy)$")
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec: PolicySpec


def parse_yaml(content: str) -> list[PolicyYaml]:
    documents = list(yaml.safe_load_all(content))
    return [PolicyYaml(**doc) for doc in documents if doc]
