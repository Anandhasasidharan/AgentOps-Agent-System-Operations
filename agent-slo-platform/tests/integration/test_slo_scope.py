import uuid

from agent_slo.models import Agent, ServiceLevelIndicator, Tenant


async def test_api_persists_scope_and_filters_status(client, tenant, agent, sli_task_success):
    response = await client.post(
        "/api/v1/slos",
        headers={"X-API-Key": tenant.slug},
        json={
            "sli_id": str(sli_task_success.id),
            "agent_id": str(agent.id),
            "name": "scoped",
            "target": 0.95,
            "comparator": "gt",
            "window": "7d",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["agent_id"] == str(agent.id)
    response = await client.get(
        "/api/v1/status", headers={"X-API-Key": tenant.slug}, params={"agent_id": str(agent.id)}
    )
    assert [s["slo_name"] for s in response.json()] == ["scoped"]
    response = await client.get(
        "/api/v1/status", headers={"X-API-Key": tenant.slug}, params={"agent_id": str(uuid.uuid4())}
    )
    assert response.json() == []


async def test_slo_rejects_foreign_and_missing_references(
    client, session, tenant, agent, sli_task_success
):
    other = Tenant(slug="other", name="Other")
    session.add(other)
    await session.flush()
    foreign_agent = Agent(tenant_id=other.id, name="private", environment="production")
    foreign_sli = ServiceLevelIndicator(
        tenant_id=other.id, name="private", metric_type="ratio", source="otel", config={}
    )
    session.add_all([foreign_agent, foreign_sli])
    await session.commit()
    for agent_id, sli_id in [
        (foreign_agent.id, sli_task_success.id),
        (uuid.uuid4(), sli_task_success.id),
        (agent.id, foreign_sli.id),
        (agent.id, uuid.uuid4()),
    ]:
        response = await client.post(
            "/api/v1/slos",
            headers={"X-API-Key": tenant.slug},
            json={
                "sli_id": str(sli_id),
                "agent_id": str(agent_id),
                "name": "forbidden",
                "target": 0.95,
                "comparator": "gt",
                "window": "7d",
            },
        )
        assert response.status_code == 404, response.text


async def test_scoped_sli_supplies_scope_and_rejects_conflicts(
    client, session, tenant, agent, sli_task_success
):
    second = Agent(tenant_id=tenant.id, name="second", environment="production")
    session.add(second)
    sli_task_success.agent_id = agent.id
    await session.commit()
    payload = {
        "sli_id": str(sli_task_success.id),
        "name": "inherited",
        "target": 0.95,
        "comparator": "gt",
        "window": "7d",
    }
    response = await client.post("/api/v1/slos", headers={"X-API-Key": tenant.slug}, json=payload)
    assert response.status_code == 201
    assert response.json()["agent_id"] == str(agent.id)
    response = await client.post(
        "/api/v1/slos",
        headers={"X-API-Key": tenant.slug},
        json={**payload, "agent_id": str(second.id)},
    )
    assert response.status_code == 422
