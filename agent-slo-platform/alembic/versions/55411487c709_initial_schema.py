"""Initial schema

Revision ID: 55411487c709
Revises:
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '55411487c709'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("framework", sa.String(length=64), nullable=True),
        sa.Column("model_provider", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "environment", "name"),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"], unique=False)

    op.create_table(
        "slis",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("metric_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slis_tenant_id", "slis", ["tenant_id"], unique=False)
    op.create_index("ix_slis_name", "slis", ["name"], unique=False)

    op.create_table(
        "slos",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sli_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("comparator", sa.String(length=8), nullable=False),
        sa.Column("window", sa.String(length=16), nullable=False),
        sa.Column("burn_rate_alert_thresholds", sa.JSON(), nullable=False),
        sa.Column("risk_budget", sa.JSON(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["sli_id"], ["slis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slos_tenant_id", "slos", ["tenant_id"], unique=False)

    op.create_table(
        "metrics",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sli_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["sli_id"], ["slis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_lookup", "metrics", ["tenant_id", "sli_id", "agent_id", "timestamp"], unique=False)
    op.create_index("ix_metrics_timestamp", "metrics", ["timestamp"], unique=False)

    op.create_table(
        "error_budgets",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("slo_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_budget", sa.Float(), nullable=False),
        sa.Column("consumed", sa.Float(), nullable=False),
        sa.Column("remaining", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["slo_id"], ["slos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slo_id", "period_start"),
    )
    op.create_index("ix_error_budgets_slo_id", "error_budgets", ["slo_id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("slo_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("burn_rate", sa.Float(), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["slo_id"], ["slos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_tenant_id", "alerts", ["tenant_id"], unique=False)
    op.create_index("ix_alerts_slo_id", "alerts", ["slo_id"], unique=False)

    op.create_table(
        "otel_spans",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.LargeBinary(), nullable=False),
        sa.Column("span_id", sa.LargeBinary(), nullable=False),
        sa.Column("parent_span_id", sa.LargeBinary(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("status", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_otel_spans_trace", "otel_spans", ["trace_id", "span_id"], unique=False)
    op.create_index("ix_otel_spans_tenant_id", "otel_spans", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_otel_spans_tenant_id", table_name="otel_spans")
    op.drop_index("ix_otel_spans_trace", table_name="otel_spans")
    op.drop_table("otel_spans")
    op.drop_index("ix_alerts_slo_id", table_name="alerts")
    op.drop_index("ix_alerts_tenant_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_error_budgets_slo_id", table_name="error_budgets")
    op.drop_table("error_budgets")
    op.drop_index("ix_metrics_timestamp", table_name="metrics")
    op.drop_index("ix_metrics_lookup", table_name="metrics")
    op.drop_table("metrics")
    op.drop_index("ix_slos_tenant_id", table_name="slos")
    op.drop_table("slos")
    op.drop_index("ix_slis_name", table_name="slis")
    op.drop_index("ix_slis_tenant_id", table_name="slis")
    op.drop_table("slis")
    op.drop_index("ix_agents_tenant_id", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
