"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = None
    target_type: str = Field(..., pattern=r"^(llm|tool|rag|mcp)$")
    failure_mode: str = Field(..., max_length=32)
    config: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str = Field(
        default="graceful_degradation",
        pattern=r"^(graceful_degradation|fail_fast|retry_success|fallback_used|error_handled)$",
    )
    agent_should_survive: bool = True
    enabled: bool = True


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    target_type: str
    failure_mode: str
    config: dict[str, Any]
    expected_behavior: str
    agent_should_survive: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ExperimentRunRequest(BaseModel):
    scenario_id: uuid.UUID
    agent_id: str = Field(..., max_length=128)
    target_override: str | None = Field(default=None, pattern=r"^(llm|tool|rag|mcp)$")
    failure_mode_override: str | None = None
    config_override: dict[str, Any] | None = None


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    scenario_id: uuid.UUID
    scenario_name: str
    target_type: str
    failure_mode: str
    agent_id: str
    status: str
    injection_successful: bool
    injection_details: dict[str, Any]
    agent_survived: bool | None
    agent_behavior: str | None
    agent_response_time_ms: float | None
    agent_error: str | None
    resilience_score: float | None
    created_at: datetime
    completed_at: datetime | None


class ExperimentReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    summary: dict[str, Any]
    overall_score: float | None
    ci_run_id: str | None
    ci_provider: str | None
    created_at: datetime


class FaultLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    experiment_id: uuid.UUID
    tenant_id: uuid.UUID
    target_type: str
    failure_mode: str
    injected_fault: dict[str, Any]
    agent_request: dict[str, Any] | None
    agent_response: dict[str, Any] | None
    injection_time_ms: float
    response_time_ms: float | None
    created_at: datetime


class ResilienceScoreSummary(BaseModel):
    total_experiments: int
    passed: int
    failed: int
    pass_rate: float
    avg_resilience_score: float
    worst_performing_target: str | None
    recommendations: list[str]


class ExperimentBatchRequest(BaseModel):
    agent_id: str = Field(..., max_length=128)
    scenarios: list[uuid.UUID] = Field(default_factory=list)
    run_all_enabled: bool = False
