import pytest
import httpx
from agentops import AgentOpsSDK


@pytest.fixture
def sdk():
    return AgentOpsSDK(api_key="test-key")


@pytest.mark.asyncio
async def test_create_tenant(sdk, respx_mock):
    respx_mock.post("http://localhost:8000/api/v1/tenants").respond(
        200, json={"id": "abc", "slug": "test", "name": "Test"}
    )
    result = await sdk.create_tenant(slug="test", name="Test")
    assert result["slug"] == "test"
    await sdk.close()


@pytest.mark.asyncio
async def test_intercept(sdk, respx_mock):
    respx_mock.post("http://localhost:8001/v1/intercept").respond(
        200, json={"allowed": True, "decision": "allow"}
    )
    result = await sdk.intercept(
        agent_id="agent-1", tool_name="read_file", tool_input={"path": "/tmp/x"}
    )
    assert result["allowed"] is True
    await sdk.close()


@pytest.mark.asyncio
async def test_create_policy(sdk, respx_mock):
    respx_mock.post("http://localhost:8001/api/v1/policies").respond(
        200, json={"id": "abc", "name": "test-policy"}
    )
    result = await sdk.create_policy(
        name="test-policy",
        policy_type="tool_blocklist",
        conditions={"tools": ["rm"]},
    )
    assert result["name"] == "test-policy"
    await sdk.close()


@pytest.mark.asyncio
async def test_resilience_score(sdk, respx_mock):
    respx_mock.get("http://localhost:8002/api/v1/resilience-score").respond(
        200, json={"overall_score": 85.0}
    )
    result = await sdk.get_resilience_score()
    assert result["overall_score"] == 85.0
    await sdk.close()


@pytest.mark.asyncio
async def test_setup_demo(sdk, respx_mock):
    respx_mock.post("http://localhost:8000/api/v1/tenants").respond(
        200, json={"id": "t1", "slug": "demo", "name": "Demo Tenant"}
    )
    respx_mock.post("http://localhost:8000/api/v1/agents").respond(
        200, json={"id": "a1", "name": "demo-agent"}
    )
    respx_mock.post("http://localhost:8000/api/v1/slis").respond(
        200, json={"id": "sli1", "name": "task-success-rate"}
    )
    respx_mock.post("http://localhost:8000/api/v1/slos").respond(
        200, json={"id": "slo1", "name": "95% success rate"}
    )
    respx_mock.post("http://localhost:8001/api/v1/policies").respond(
        200, json={"id": "p1", "name": "block-dangerous-commands"}
    )
    respx_mock.post("http://localhost:8002/api/v1/scenarios/seed").respond(
        200, json=[{"id": "s1"}]
    )
    result = await sdk.setup_demo()
    assert result["tenant"]["slug"] == "demo"
    assert result["scenarios_count"] == 1
    await sdk.close()
