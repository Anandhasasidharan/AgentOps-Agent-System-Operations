from __future__ import annotations

import os

os.environ["NATS_URL"] = ""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.api import app

client = TestClient(app)


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
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        resp = ws.receive_json()
        assert resp == {"type": "pong"}


def test_websocket_multiple_clients():
    with client.websocket_connect("/ws") as ws1:
        with client.websocket_connect("/ws") as ws2:
            ws1.send_text("ping")
            assert ws1.receive_json() == {"type": "pong"}
            ws2.send_text("ping")
            assert ws2.receive_json() == {"type": "pong"}
