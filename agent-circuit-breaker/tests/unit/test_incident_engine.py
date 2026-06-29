"""Tests for the Incident Engine."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.incident_engine import create_incident, get_active_incidents, resolve_incident


@pytest.mark.asyncio
async def test_create_incident(session):
    tenant_id = uuid.uuid4()
    incident = await create_incident(
        session, tenant_id, "agent-1", "session-1",
        severity="critical", category="policy_violation",
        message="Blocked delete_file",
        details={"tool_name": "delete_file"},
        action_taken="block",
    )
    assert incident.id is not None
    assert incident.severity == "critical"
    assert incident.resolved_at is None


@pytest.mark.asyncio
async def test_get_active_incidents(session):
    tenant_id = uuid.uuid4()
    await create_incident(
        session, tenant_id, "agent-1", None,
        severity="warning", category="anomaly",
        message="High anomaly score",
        details={},
        action_taken="alert",
    )
    incidents = await get_active_incidents(session, tenant_id)
    assert len(incidents) == 1

    incidents2 = await get_active_incidents(session, tenant_id, agent_id="agent-1")
    assert len(incidents2) == 1

    incidents3 = await get_active_incidents(session, tenant_id, agent_id="agent-2")
    assert len(incidents3) == 0


@pytest.mark.asyncio
async def test_resolve_incident(session):
    tenant_id = uuid.uuid4()
    incident = await create_incident(
        session, tenant_id, "agent-1", None,
        severity="info", category="policy_violation",
        message="Test",
        details={},
        action_taken="block",
    )
    assert incident.resolved_at is None

    resolved = await resolve_incident(session, incident.id)
    assert resolved is not None
    assert resolved.resolved_at is not None
