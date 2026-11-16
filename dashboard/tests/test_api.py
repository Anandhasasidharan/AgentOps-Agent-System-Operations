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
    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/events", auth=("operator", "tenant:secret"))
        assert response.status_code == 200


async def test_unconfigured_dashboard_denies_access(monkeypatch):
    monkeypatch.setattr("dashboard.api.API_KEY", "")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/")).status_code == 401


async def test_event_data_is_rendered_as_text(monkeypatch):
    import json
    import re
    import shutil
    import subprocess
    from unittest.mock import AsyncMock

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the dashboard JavaScript regression")
    monkeypatch.setattr("dashboard.api.API_KEY", "tenant:secret")
    monkeypatch.setattr(
        "dashboard.api._check", AsyncMock(return_value={"status": "ok", "data": {}})
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/", headers={"X-API-Key": "tenant:secret"})
    assert response.status_code == 200
    script = re.search(r"<script>(.*?)</script>", response.text, re.S).group(1)
    attack = '<img src=x onerror="globalThis.compromised=true">'
    event = {
        "event_type": "agentops.cb." + attack,
        "payload": {"agent_id": attack, "input": attack},
    }
    # Execute the delivered client code. Nonempty HTML assignments are rejected,
    # while DOM text nodes retain the original untrusted strings.
    harness = r"""
const {script, event, attack} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const assert = require('assert');
class Element {
  constructor() { this.children = []; this.style = {}; this.textContent = ''; }
  set innerHTML(value) { assert.strictEqual(value, '', 'Untrusted HTML sink used'); this.children = []; }
  append(...children) { this.children.push(...children); }
  insertBefore(child) { this.children.unshift(child); }
  get firstChild() { return this.children[0]; }
  get lastChild() { return this.children.at(-1); }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
}
const list = new Element(), badge = new Element();
global.document = {createElement: () => new Element(), getElementById: id => id === 'event-list' ? list : badge};
global.WebSocket = class {constructor() {global.socket = this;}};
require('vm').runInThisContext(script);
socket.onopen();
socket.onmessage({data: JSON.stringify(event)});
assert.strictEqual(list.children.length, 1);
const texts = list.children[0].children.map(child => child.textContent);
assert(texts.includes(attack), 'Agent name must remain plain text');
assert(texts.some(text => text.includes('"input"')), 'Payload must remain text');
assert.strictEqual(global.compromised, undefined);
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps({"script": script, "event": event, "attack": attack}),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
