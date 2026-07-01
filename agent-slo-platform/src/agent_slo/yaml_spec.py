"""YAML SLO specification parser."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Metadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(..., max_length=128)
    tenant: str = Field(..., max_length=64)
    environment: str = Field(default="production", max_length=32)
    agent: str | None = Field(default=None, max_length=128)


class BurnRateAlertSpec(BaseModel):
    threshold: float = Field(..., gt=0, le=1)
    severity: str = Field(..., pattern="^(info|warning|critical)$")


class SLOSpec(BaseModel):
    sli: str = Field(..., max_length=64)
    target: float = Field(..., gt=0)
    comparator: str = Field(..., pattern="^(gt|lt|eq)$")
    window: str = Field(..., max_length=16)
    burn_rate_alerts: list[BurnRateAlertSpec] = Field(
        default_factory=lambda: [
            BurnRateAlertSpec(threshold=0.02, severity="info"),
            BurnRateAlertSpec(threshold=0.05, severity="warning"),
            BurnRateAlertSpec(threshold=0.10, severity="critical"),
        ],
        alias="burnRateAlerts",
    )
    labels: dict[str, str] = Field(default_factory=dict)


class RiskBudgetWeightSpec(BaseModel):
    budget: float = Field(..., gt=0)
    window: str = Field(..., max_length=16)
    weights: dict[str, float] = Field(default_factory=dict)
    action: str = Field(default="require_approval", pattern="^(require_approval|kill|log)$")
    burn_rate_alerts: list[BurnRateAlertSpec] = Field(default_factory=list, alias="burnRateAlerts")


class SLOYaml(BaseModel):
    api_version: str = Field(..., alias="apiVersion")
    kind: str = Field(..., pattern="^(SLO|RiskBudget)$")
    metadata: Metadata
    spec: SLOSpec | RiskBudgetWeightSpec

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        if v != "agentops.io/v1":
            raise ValueError("Unsupported apiVersion; expected agentops.io/v1")
        return v


def parse_yaml(content: str) -> list[SLOYaml]:
    documents = list(yaml.safe_load_all(content))
    return [SLOYaml(**doc) for doc in documents if doc]


def window_to_seconds(window: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(window) < 2 or window[-1] not in units:
        raise ValueError(f"Invalid window format: {window}")
    return int(window[:-1]) * units[window[-1]]
