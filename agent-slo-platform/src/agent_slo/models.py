"""SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map: dict[Any, Any] = {
        dict[str, Any]: JSON,
        list[dict[str, Any]]: JSON,
        list[float]: JSON,
    }


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    agents: Mapped[list["Agent"]] = relationship(back_populates="tenant")
    slos: Mapped[list["ServiceLevelObjective"]] = relationship(back_populates="tenant")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("tenant_id", "environment", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    framework: Mapped[str | None] = mapped_column(String(64))
    model_provider: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=now_utc)

    tenant: Mapped["Tenant"] = relationship(back_populates="agents")


class ServiceLevelIndicator(Base):
    __tablename__ = "slis"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    tenant: Mapped["Tenant"] = relationship()


class ServiceLevelObjective(Base):
    __tablename__ = "slos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    sli_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slis.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    target: Mapped[float] = mapped_column(nullable=False)
    comparator: Mapped[str] = mapped_column(String(8), nullable=False)
    window: Mapped[str] = mapped_column(String(16), nullable=False)
    burn_rate_alert_thresholds: Mapped[list[float]] = mapped_column(JSON, default=list)
    risk_budget: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    tenant: Mapped["Tenant"] = relationship(back_populates="slos")
    sli: Mapped["ServiceLevelIndicator"] = relationship()


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (Index("ix_metrics_lookup", "tenant_id", "sli_id", "agent_id", "timestamp"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    sli_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slis.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)
    value: Mapped[float] = mapped_column(nullable=False)
    count: Mapped[int] = mapped_column(default=1)
    window_start: Mapped[datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime] = mapped_column(nullable=False)


class ErrorBudget(Base):
    __tablename__ = "error_budgets"
    __table_args__ = (UniqueConstraint("slo_id", "period_start"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slos.id"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    total_budget: Mapped[float] = mapped_column(nullable=False)
    consumed: Mapped[float] = mapped_column(default=0.0)
    remaining: Mapped[float] = mapped_column(default=0.0)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    slo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slos.id"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float] = mapped_column(nullable=False)
    burn_rate: Mapped[float] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(String(512))
    fired_at: Mapped[datetime] = mapped_column(default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class OtelSpan(Base):
    __tablename__ = "otel_spans"
    __table_args__ = (Index("ix_otel_spans_trace", "trace_id", "span_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[bytes] = mapped_column(nullable=False)
    span_id: Mapped[bytes] = mapped_column(nullable=False)
    parent_span_id: Mapped[bytes | None] = mapped_column(nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(default=now_utc)
