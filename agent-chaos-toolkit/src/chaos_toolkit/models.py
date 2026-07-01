"""SQLAlchemy models for Chaos Toolkit."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agentops_core.base import Base, now_utc
from sqlalchemy import JSON, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class Scenario(Base):
    """A chaos experiment scenario definition."""

    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))

    # Target: llm, tool, rag, mcp
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # Failure mode
    failure_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    # llm: model_downgrade, timeout, hallucination, refusal
    # tool: timeout, crash, bad_output, wrong_data
    # rag: no_results, bad_data, corrupted_context, slow_response
    # mcp: server_down, timeout, bad_capabilities, auth_failure

    # Injection configuration
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Success criteria
    expected_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    # graceful_degradation, fail_fast, retry_success, fallback_used, error_handled

    # Whether the agent is expected to survive (pass) this scenario
    agent_should_survive: Mapped[bool] = mapped_column(default=True)

    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)


class Experiment(Base):
    """A single run of a chaos experiment."""

    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_tenant", "tenant_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    scenario_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(128))

    target_type: Mapped[str] = mapped_column(String(16))
    failure_mode: Mapped[str] = mapped_column(String(32))

    # Agent identifier under test
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Status: running, completed, failed, aborted
    status: Mapped[str] = mapped_column(String(16), default="running")

    # Injection result
    injection_successful: Mapped[bool] = mapped_column(default=False)
    injection_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Agent response
    agent_survived: Mapped[bool | None] = mapped_column(nullable=True)
    agent_behavior: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_response_time_ms: Mapped[float | None] = mapped_column(nullable=True)
    agent_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Resilience score
    resilience_score: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ExperimentReport(Base):
    """Aggregated report for a set of experiments."""

    __tablename__ = "experiment_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))

    # JSON summary of all experiments in this report
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Overall resilience score
    overall_score: Mapped[float | None] = mapped_column(nullable=True)

    # CI metadata
    ci_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ci_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)


class FaultLog(Base):
    """Detailed log of a single fault injection."""

    __tablename__ = "fault_logs"
    __table_args__ = (Index("ix_fault_logs_experiment", "experiment_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    target_type: Mapped[str] = mapped_column(String(16))
    failure_mode: Mapped[str] = mapped_column(String(32))

    # What was injected
    injected_fault: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # What the agent did
    agent_request: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    agent_response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timing
    injection_time_ms: Mapped[float] = mapped_column(default=0.0)
    response_time_ms: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)
