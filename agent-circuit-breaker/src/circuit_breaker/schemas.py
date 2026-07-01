"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PolicyCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = Field(default=None, max_length=512)
    enabled: bool = True
    priority: int = 0
    policy_type: str = Field(
        ...,
        pattern=r"^(tool_allowlist|tool_blocklist|rate_limit|token_budget|risk_threshold|anomaly_threshold|time_window|reasoning_loop)$",
    )
    conditions: dict[str, Any] = Field(default_factory=dict)
    action: str = Field(default="block", pattern=r"^(allow|block|reroute|kill|alert)$")
    action_config: dict[str, Any] | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    enabled: bool
    priority: int
    policy_type: str
    conditions: dict[str, Any]
    action: str
    action_config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ToolCallIn(BaseModel):
    agent_id: str = Field(..., max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    tool_name: str = Field(..., max_length=128)
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: dict[str, Any] | None = None
    duration_ms: float | None = None
    token_count: int | None = None
    cost: float | None = None


class ToolCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: str
    session_id: str | None
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any] | None
    duration_ms: float | None
    token_count: int | None
    cost: Decimal | None
    risk_score: float | None
    anomaly_score: float | None
    is_suspicious: bool
    decision: str | None
    decision_reason: str | None
    blocked: bool
    timestamp: datetime


class InterceptResponse(BaseModel):
    allowed: bool
    decision: str
    reason: str | None = None
    risk_score: float | None = None
    incident_id: uuid.UUID | None = None
    tool_call_id: uuid.UUID | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: str
    session_id: str | None
    severity: str
    category: str
    message: str
    details: dict[str, Any]
    action_taken: str
    tool_call_id: uuid.UUID | None
    rollback_id: uuid.UUID | None
    rolled_back: bool
    created_at: datetime
    resolved_at: datetime | None


class KillSwitchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: str
    reason: str
    triggered_by: str
    active: bool
    expires_at: datetime | None
    created_at: datetime
    released_at: datetime | None


class AgentStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: str
    window_start: datetime
    window_end: datetime
    call_count: int
    unique_tools: list[str]
    total_tokens: int
    total_cost: float
    failure_count: int
    anomaly_count: int
    max_risk_score: float
    is_killed: bool
    avg_duration_ms: float | None
    tool_entropy: float | None


class AgentStatusResponse(BaseModel):
    agent_id: str
    is_killed: bool
    state: AgentStateOut | None
    active_incidents: list[IncidentOut]
    recent_decisions: list[dict[str, Any]]
