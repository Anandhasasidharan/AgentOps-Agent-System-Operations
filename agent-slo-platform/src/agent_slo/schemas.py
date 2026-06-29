"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    created_at: datetime


class AgentCreate(BaseModel):
    environment: str = Field(default="production", max_length=32)
    name: str = Field(..., max_length=128)
    framework: str | None = Field(default=None, max_length=64)
    model_provider: str | None = Field(default=None, max_length=64)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    environment: str
    name: str
    framework: str | None
    model_provider: str | None
    created_at: datetime


class SLICreate(BaseModel):
    name: str = Field(..., max_length=64)
    metric_type: str = Field(..., pattern="^(ratio|threshold|budget|count)$")
    source: str = Field(..., max_length=32)
    config: dict[str, Any] = Field(default_factory=dict)


class SLIOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID | None
    name: str
    metric_type: str
    source: str
    config: dict[str, Any]


class SLOCreate(BaseModel):
    sli_id: uuid.UUID
    name: str = Field(..., max_length=128)
    description: str | None = Field(default=None, max_length=512)
    target: float = Field(..., gt=0, le=1)
    comparator: str = Field(..., pattern="^(gt|lt|eq)$")
    window: str = Field(..., max_length=16)
    burn_rate_alert_thresholds: list[dict[str, Any]] = Field(default_factory=lambda: [
                {"threshold": 0.02, "severity": "info"},
                {"threshold": 0.05, "severity": "warning"},
                {"threshold": 0.10, "severity": "critical"},
            ])
    risk_budget: dict[str, Any] | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class SLOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID | None
    sli_id: uuid.UUID
    name: str
    description: str | None
    target: float
    comparator: str
    window: str
    burn_rate_alert_thresholds: list[dict[str, Any]]
    risk_budget: dict[str, Any] | None
    labels: dict[str, str]
    created_at: datetime
    updated_at: datetime


class StatusEntry(BaseModel):
    slo_id: uuid.UUID
    slo_name: str
    sli_name: str
    window: str
    target: float
    current_value: float
    comparator: str
    is_breaching: bool
    budget_consumed: float
    budget_remaining: float
    burn_rate: float
    alert_severity: str | None


class MetricIn(BaseModel):
    sli_id: uuid.UUID
    timestamp: datetime
    value: float
    count: int = 1


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID | None
    sli_id: uuid.UUID
    timestamp: datetime
    value: float
    count: int


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    slo_id: uuid.UUID
    severity: str
    threshold: float
    burn_rate: float
    message: str
    fired_at: datetime
    resolved_at: datetime | None


class ComplianceReport(BaseModel):
    generated_at: datetime
    standard: str
    tenant: str
    controls: list[dict[str, Any]]
