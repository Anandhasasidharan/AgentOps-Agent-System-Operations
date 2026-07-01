"""SQLAlchemy models for Circuit Breaker."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentops_core.base import Base, now_utc


class Policy(Base):
    """A policy rule that determines what actions are allowed or blocked."""

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=0)

    # Policy type: tool_allowlist, tool_blocklist, rate_limit, token_budget,
    # risk_threshold, anomaly_threshold, time_window
    policy_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # The condition as JSON: {"match": {"tool_name": "delete_file"}, "action": "block"}
    # or {"match": {"tool_name": "*"}, "max_calls": 100, "window": "5m", "action": "block"}
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Action on match: allow, block, reroute, kill, alert
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="block")

    # Optional: action parameters (e.g. reroute URL, alert webhook)
    action_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)


class ToolCall(Base):
    """Record of every tool call intercepted by the circuit breaker."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_calls_tenant", "tenant_id", "timestamp"),
        Index("ix_tool_calls_agent", "agent_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tool_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    token_count: Mapped[int | None] = mapped_column(nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(nullable=True)

    # Risk assessment
    risk_score: Mapped[float | None] = mapped_column(nullable=True)
    anomaly_score: Mapped[float | None] = mapped_column(nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(default=False)

    # Decision
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blocked: Mapped[bool] = mapped_column(default=False)

    timestamp: Mapped[datetime] = mapped_column(default=now_utc, index=True)


class AgentState(Base):
    """Current state of an agent — windowed counters for rate limiting / anomaly detection."""

    __tablename__ = "agent_states"
    __table_args__ = (UniqueConstraint("tenant_id", "agent_id", "window_start"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)

    window_start: Mapped[datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime] = mapped_column(nullable=False)

    call_count: Mapped[int] = mapped_column(default=0)
    unique_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    total_tokens: Mapped[int] = mapped_column(default=0)
    total_cost: Mapped[float] = mapped_column(default=0.0)
    failure_count: Mapped[int] = mapped_column(default=0)
    anomaly_count: Mapped[int] = mapped_column(default=0)
    max_risk_score: Mapped[float] = mapped_column(default=0.0)
    is_killed: Mapped[bool] = mapped_column(default=False)

    # Behavioral profile — rolling averages for drift detection
    avg_duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    tool_entropy: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)


class Incident(Base):
    """An incident created when the circuit breaker triggers."""

    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_tenant", "tenant_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Severity: info, warning, critical, fatal
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # anomaly, policy_violation, risk_exceeded, reasoning_loop, cost_explosion

    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # The decision taken
    action_taken: Mapped[str] = mapped_column(String(16), nullable=False)
    # alert, reroute, block, kill

    # Linked tool call that triggered the incident
    tool_call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tool_calls.id"), nullable=True
    )

    # Rollback reference
    rollback_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    rolled_back: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RollbackLog(Base):
    """Log of rollback operations."""

    __tablename__ = "rollback_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)

    rollback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # tool_call_compensation, state_restore, cost_refund, approval_revoke

    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending, completed, failed

    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class KillSwitch(Base):
    """Kill switch records — when an agent is hard-killed."""

    __tablename__ = "kill_switches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False)
    # policy, anomaly, manual, risk_budget

    active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)
