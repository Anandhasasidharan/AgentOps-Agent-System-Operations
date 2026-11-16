from __future__ import annotations

import os

os.environ["NATS_URL"] = ""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.api import app

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
client = TestClient(app, headers={"X-API-Key": "test:token"})


@pytest.fixture(autouse=True)
def authenticated_tenant():
    async def validate(key):
        return TENANT if key == "test:token" else None

    with patch("gateway.api._validate_key", side_effect=validate):
        yield


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "nats_connected" in data
    assert data["nats_connected"] is False


def test_metrics():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "gw_events_published_total" in resp.text


def test_events_empty():
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    assert resp.json() == []


def test_events_with_since():
    resp = client.get("/api/v1/events?since=2000-01-01T00:00:00")
    assert resp.status_code == 200


def test_events_invalid_since():
    resp = client.get("/api/v1/events?since=not-a-date")
    assert resp.status_code == 400


def test_cors_headers():
    resp = client.options(
        "/api/v1/events",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_websocket_ping():
    with client.websocket_connect("/ws?api_key=test:token") as ws:
        ws.send_text("ping")
        resp = ws.receive_json()
        assert resp == {"type": "pong"}


def test_websocket_multiple_clients():
    with client.websocket_connect("/ws?api_key=test:token") as ws1:
        with client.websocket_connect("/ws?api_key=test:token") as ws2:
            ws1.send_text("ping")
            assert ws1.receive_json() == {"type": "pong"}
            ws2.send_text("ping")
            assert ws2.receive_json() == {"type": "pong"}


def test_events_require_header():
    assert TestClient(app).get("/api/v1/events").status_code == 401
    assert TestClient(app).get("/api/v1/events?x_api_key=test:token").status_code == 401


def test_websocket_requires_key():
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass


def test_history_is_tenant_scoped():
    from gateway.api import event_buffer

    event_buffer.extend(
        [
            {"tenant_id": TENANT, "timestamp": "2026-01-01T00:00:00+00:00"},
            {"tenant_id": "other", "timestamp": "2026-01-01T00:00:00+00:00"},
        ]
    )
    try:
        result = client.get("/api/v1/events").json()
        assert len(result) == 1
        assert result[0]["tenant_id"] == TENANT
    finally:
        event_buffer.clear()


@pytest.mark.asyncio
async def test_broadcast_is_tenant_scoped():
    from agentops_events import make_event
    from gateway.api import broadcast, ws_clients, event_buffer
    import uuid

    first, second = AsyncMock(), AsyncMock()
    ws_clients.update({first: TENANT, second: "other"})
    try:
        await broadcast(make_event("test", "agentops.cb.intercept.allow", uuid.UUID(TENANT), {}))
        first.send_json.assert_awaited_once()
        second.send_json.assert_not_awaited()
    finally:
        ws_clients.clear()
        event_buffer.clear()
