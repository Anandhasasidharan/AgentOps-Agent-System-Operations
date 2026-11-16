from httpx import ASGITransport, AsyncClient

from dashboard.api import app


async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_dashboard_requires_auth(monkeypatch):
    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/")).status_code == 401
        assert (await c.get("/events")).status_code == 401
        assert (await c.get("/events", headers={"X-API-Key": "wrong"})).status_code == 401


async def test_authorized_dashboard_request(monkeypatch):
    import httpx

    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")

    def receive(request):
        assert request.headers["X-API-Key"] == "tenant:secret"
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as upstream:
        monkeypatch.setattr("dashboard.api._client", upstream)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get("/events", auth=("operator", "tenant:secret"))
            assert response.status_code == 200


async def test_unconfigured_dashboard_denies_access(monkeypatch):
    monkeypatch.setattr("dashboard.api.API_KEY", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/")).status_code == 401


async def test_event_data_is_rendered_as_text(monkeypatch):
    import json
    import shutil
    import subprocess
    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the dashboard JavaScript regression")
    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/", headers={"X-API-Key": "tenant:secret"})
        response = await client.get("/static/render.js")
    assert page.status_code == response.status_code == 200
    assert "tenant:secret" not in page.text
    attack = '<img src=x onerror="globalThis.compromised=true">'
    event = {
        "event_type": "agentops.cb." + attack,
        "payload": {"agent_id": attack, "input": attack},
    }
    harness = r"""
const {script,event,attack}=JSON.parse(require('fs').readFileSync(0,'utf8'));
const assert=require('assert');
class Element {
 constructor(){this.children=[];this.style={};this.textContent='';}
 set innerHTML(value){assert.strictEqual(value,'','Unsafe HTML sink used');}
 setAttribute(){} addEventListener(){} append(...nodes){this.children.push(...nodes);}
}
global.document={createElement:()=>new Element(),createTextNode:text=>({textContent:text})};
require('vm').runInThisContext(script);
const row=AgentOpsRender.eventRow(event);
assert.strictEqual(row.children.length,4);
assert(row.children.some(n=>n.textContent===attack));
assert(row.children.some(n=>n.textContent.includes('"input"')));
assert.strictEqual(global.compromised,undefined);
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps({"script": response.text, "event": event, "attack": attack}),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


async def test_aggregate_health_checks_gateway_and_nats(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    check = AsyncMock(return_value={"status": "ok", "data": {"nats_connected": True}})
    monkeypatch.setattr("dashboard.api._check", check)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health", headers={"X-API-Key": "tenant:secret"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert check.await_count == 4
    assert "nats" in response.json()["services"]


async def test_proxy_is_authenticated_scoped_and_preserves_validation(monkeypatch):
    import httpx

    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    seen = []

    def receive(request):
        seen.append(request)
        return httpx.Response(422, json={"detail": "Invalid conditions"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as upstream:
        monkeypatch.setattr("dashboard.api._client", upstream)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (
                await client.post("/api/services/breaker/api/v1/policies", json={})
            ).status_code == 401
            page = await client.get("/", auth=("operator", "tenant:secret"))
            assert page.cookies.get("agentops_session")
            assert "httponly" in page.headers["set-cookie"].lower()
            response = await client.post(
                "/api/services/breaker/api/v1/policies", json={"name": "test"}
            )
            assert response.status_code == 422
            assert response.json()["detail"] == "Invalid conditions"
            assert seen[-1].headers["X-API-Key"] == "tenant:secret"
            assert (
                await client.post("/api/services/slo/api/v1/keys/rotate", json={})
            ).status_code == 404
            assert (
                await client.post(
                    "/api/services/breaker/api/v1/policies",
                    json={},
                    headers={"Origin": "http://evil.test"},
                )
            ).status_code == 403


async def test_snapshot_keeps_independent_resource_errors(monkeypatch):
    import httpx

    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")

    def receive(request):
        if request.url.path == "/api/v1/policies":
            return httpx.Response(503, json={"detail": "down"})
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as upstream:
        monkeypatch.setattr("dashboard.api._client", upstream)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/snapshot", headers={"X-API-Key": "tenant:secret"})
    assert response.status_code == 200
    assert response.json()["data"]["policies"] is None
    assert response.json()["data"]["agents"] == []
    assert any("policies" in error for error in response.json()["errors"])
