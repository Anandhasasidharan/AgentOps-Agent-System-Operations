"""Regression tests for scripts/seed.py.

The script must accept the API's 201 responses, keep a valid API key, and
only print commands that actually exist.
"""

from __future__ import annotations

import importlib.util
import json
import shlex
from pathlib import Path
from urllib.parse import urlparse

import pytest

SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeAPI:
    """Minimal router for the endpoints seed.py touches."""

    def __init__(self) -> None:
        self.tenant_status = 201
        self.tenant_payload = {"api_key": "acme-corp:s3cr3t", "slug": "acme-corp"}
        self.calls: list[tuple[str, str, dict | None, float | None]] = []
        self.experiment_body: dict | None = None
        self.scenarios = [
            {"id": "s-timeout", "name": "llm-timeout", "failure_mode": "timeout"},
            {"id": "s-crash", "name": "tool-crash", "failure_mode": "crash"},
        ]

    def get(self, url: str, headers=None, timeout=None) -> FakeResponse:
        path = urlparse(url).path
        self.calls.append(("GET", path, None, timeout))
        if path == "/health":
            return FakeResponse(200, {})
        if path == "/api/v1/scenarios":
            return FakeResponse(200, self.scenarios)
        return FakeResponse(404, {})

    def post(self, url: str, json=None, headers=None, timeout=None) -> FakeResponse:
        path = urlparse(url).path
        self.calls.append(("POST", path, json, timeout))
        if path == "/api/v1/tenants":
            return FakeResponse(self.tenant_status, self.tenant_payload)
        if path == "/api/v1/agents":
            return FakeResponse(201, {"id": "agent-1"})
        if path == "/api/v1/slis":
            return FakeResponse(201, {"id": "sli-1"})
        if path == "/api/v1/slos":
            return FakeResponse(201, {"id": "slo-1"})
        if path == "/api/v1/scenarios/seed":
            return FakeResponse(200, self.scenarios)
        if path == "/api/v1/experiments":
            self.experiment_body = json
            return FakeResponse(201, {"id": "exp-1", "status": "completed"})
        if path == "/api/v1/policies":
            return FakeResponse(201, {"id": "policy-1"})
        if path == "/v1/intercept":
            decision = "block" if (json or {}).get("tool_name") == "rm" else "allow"
            return FakeResponse(200, {"decision": decision})
        if path == "/v1/traces":
            return FakeResponse(202, {})
        return FakeResponse(404, {})


def load_seed_module():
    spec = importlib.util.spec_from_file_location("agentops_seed", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seed(tmp_path, monkeypatch):
    # A space catches unquoted paths in the printed "Load it" command.
    env_file = tmp_path / "agent ops.env"
    monkeypatch.setenv("AGENTOPS_ENV_FILE", str(env_file))
    monkeypatch.setenv("API_KEY", "dev-api-key")
    module = load_seed_module()
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    return module, env_file


@pytest.fixture
def api(seed, monkeypatch):
    module, _ = seed
    fake = FakeAPI()
    monkeypatch.setattr(module.httpx, "get", fake.get)
    monkeypatch.setattr(module.httpx, "post", fake.post)
    return fake


def test_seed_accepts_201_creates_and_writes_the_real_key(seed, api, capsys, monkeypatch):
    module, env_file = seed
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)

    assert module.main() == 0

    out = capsys.readouterr().out
    assert "Seed complete" in out
    assert "acme-corp:s3cr3t" in out
    assert "chaosctl report" in out
    assert "chaosctl status" not in out
    assert "cbctl    status demo-agent" in out
    assert "sloctl   status" in out
    assert f". {shlex.quote(str(env_file))}; set +a" in out

    # llm-timeout blocks for 35s; the demo experiment must pick a fast scenario.
    assert api.experiment_body["scenario_id"] == "s-crash"
    assert api.experiment_body["agent_id"] == "demo-agent"
    assert any(
        path == "/api/v1/experiments" and timeout == module.EXPERIMENT_TIMEOUT
        for _, path, _, timeout in api.calls
    )

    assert env_file.exists()
    assert "API_KEY=acme-corp:s3cr3t" in env_file.read_text()
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_seed_refuses_to_continue_when_existing_tenant_has_no_key(seed, api, capsys):
    module, env_file = seed
    api.tenant_status = 409

    assert module.main() == 1

    out = capsys.readouterr().out
    assert "already exists, but no API key was supplied" in out
    assert "Re-run with API_KEY='<slug>:<token>'" in out
    assert "Seed complete" not in out
    assert not env_file.exists()
    assert not any(path == "/api/v1/agents" for _, path, _, _ in api.calls)


def test_seed_uses_a_supplied_key_when_tenant_already_exists(seed, api, capsys):
    module, env_file = seed
    module.API_KEY = "acme-corp:existing"
    module.HEADERS["X-API-Key"] = module.API_KEY
    api.tenant_status = 409

    assert module.main() == 0

    out = capsys.readouterr().out
    assert "already exists (using supplied API key)" in out
    assert "acme-corp:existing" in out
    assert "API_KEY=acme-corp:existing" in env_file.read_text()
