"""API integration tests."""

import uuid

import pytest
from httpx import AsyncClient

from chaos_toolkit.models import Scenario


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_scenario(client: AsyncClient):
    resp = await client.post(
        "/api/v1/scenarios",
        json={
            "name": "test-scenario",
            "target_type": "llm",
            "failure_mode": "timeout",
            "config": {"params": {"delay_seconds": 30}},
            "expected_behavior": "graceful_degradation",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-scenario"
    assert data["target_type"] == "llm"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_scenarios(client: AsyncClient, sample_scenario: Scenario):
    resp = await client.get("/api/v1/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_scenario(client: AsyncClient, sample_scenario: Scenario):
    resp = await client.get(f"/api/v1/scenarios/{sample_scenario.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "llm-timeout-test"


@pytest.mark.asyncio
async def test_get_scenario_not_found(client: AsyncClient):
    resp = await client.get(f"/api/v1/scenarios/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_seed_scenarios(client: AsyncClient):
    resp = await client.post("/api/v1/scenarios/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 15  # All built-in scenarios


@pytest.mark.asyncio
async def test_run_experiment(client: AsyncClient, sample_scenario: Scenario):
    resp = await client.post(
        "/api/v1/experiments",
        json={
            "scenario_id": str(sample_scenario.id),
            "agent_id": "test-agent",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["injection_successful"] is True
    assert data["agent_id"] == "test-agent"


@pytest.mark.asyncio
async def test_list_experiments(client: AsyncClient, sample_scenario: Scenario):
    # Create one first
    await client.post(
        "/api/v1/experiments",
        json={"scenario_id": str(sample_scenario.id), "agent_id": "agent-1"},
    )
    resp = await client.get("/api/v1/experiments")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_resilience_score(client: AsyncClient, sample_scenario: Scenario):
    # Run a few experiments
    for i in range(3):
        await client.post(
            "/api/v1/experiments",
            json={"scenario_id": str(sample_scenario.id), "agent_id": f"agent-{i}"},
        )

    resp = await client.get("/api/v1/resilience-score")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_experiments"] >= 3
