"""Regression tests for the shared per-tenant rate limiter."""

from __future__ import annotations

from agentops_core.rate_limiter import add_rate_limiter
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app(rpm: int) -> FastAPI:
    app = FastAPI()
    add_rate_limiter(app, rpm=rpm)

    @app.get("/api/v1/thing")
    def thing() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> str:
        return "metrics"

    return app


def test_zero_rpm_disables_rate_limiting() -> None:
    client = TestClient(_app(0))
    headers = {"X-API-Key": "acme-corp:a1b2c3"}

    for _ in range(100):
        assert client.get("/api/v1/thing", headers=headers).status_code == 200


def test_positive_rpm_still_enforces_the_window() -> None:
    client = TestClient(_app(1))
    headers = {"X-API-Key": "acme-corp:a1b2c3"}

    assert client.get("/api/v1/thing", headers=headers).status_code == 200
    limited = client.get("/api/v1/thing", headers=headers)
    assert limited.status_code == 429
    assert limited.text == "Rate limit exceeded"


def test_zero_rpm_still_allows_anonymous_traffic() -> None:
    client = TestClient(_app(0))

    for _ in range(10):
        assert client.get("/api/v1/thing").status_code == 200


def test_health_and_metrics_bypass_the_limiter() -> None:
    client = TestClient(_app(1))
    headers = {"X-API-Key": "acme-corp:a1b2c3"}

    for _ in range(5):
        assert client.get("/health", headers=headers).status_code == 200
        assert client.get("/metrics", headers=headers).status_code == 200
