"""Regression tests for the configurable chaosctl HTTP timeout."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from chaos_toolkit import cli
from chaos_toolkit.scenarios import BUILTIN_SCENARIOS

runner = CliRunner()


class _FakeResponse:
    def __init__(self, payload: dict | list | None = None) -> None:
        self._payload = payload if payload is not None else {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict | list:
        return self._payload


class _FakeClient:
    last_kwargs: dict = {}

    def __init__(self, **kwargs) -> None:
        _FakeClient.last_kwargs = kwargs

    def post(self, url: str, **kwargs) -> _FakeResponse:
        if url.endswith("/api/v1/experiments"):
            return _FakeResponse({"id": "exp-1", "resilience_score": 0.9})
        if url.endswith("/api/v1/experiments/batch"):
            return _FakeResponse([])
        if url.endswith("/api/v1/scenarios/seed"):
            return _FakeResponse([])
        return _FakeResponse({"id": "scenario-1"})

    def get(self, url: str, **kwargs) -> _FakeResponse:
        return _FakeResponse(
            {
                "total_experiments": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "avg_resilience_score": 0.0,
            }
        )


@pytest.fixture(autouse=True)
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[_FakeClient]:
    monkeypatch.setattr(cli.httpx, "Client", _FakeClient)
    _FakeClient.last_kwargs = {}
    return _FakeClient


def test_default_timeout_outlasts_llm_timeout_scenario() -> None:
    """The built-in llm-timeout scenario must not exceed the client timeout."""
    llm_timeout = next(s for s in BUILTIN_SCENARIOS if s["name"] == "llm-timeout")
    delay = llm_timeout["config"]["params"]["delay_seconds"]
    assert cli.DEFAULT_TIMEOUT > delay


@pytest.mark.parametrize(
    "args",
    [
        ["run", "scenario-1", "agent-1", "--api-key", "k"],
        ["batch", "agent-1", "--api-key", "k"],
        ["report", "--api-key", "k"],
        ["seed", "--api-key", "k"],
    ],
)
def test_every_command_uses_the_default_timeout(args: list[str]) -> None:
    result = runner.invoke(cli.app, args)

    assert result.exit_code == 0, result.output
    assert _FakeClient.last_kwargs["timeout"] == cli.DEFAULT_TIMEOUT


def test_timeout_flag_overrides_the_default() -> None:
    result = runner.invoke(cli.app, ["report", "--api-key", "k", "--timeout", "120"])

    assert result.exit_code == 0, result.output
    assert _FakeClient.last_kwargs["timeout"] == 120.0


def test_timeout_env_var_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_TIMEOUT", "90")

    result = runner.invoke(cli.app, ["report", "--api-key", "k"])

    assert result.exit_code == 0, result.output
    assert _FakeClient.last_kwargs["timeout"] == 90.0


def test_apply_uses_the_configured_timeout(tmp_path) -> None:
    path = tmp_path / "scenario.yaml"
    path.write_text(
        "apiVersion: chaosops.io/v1\n"
        "kind: ChaosScenario\n"
        "metadata:\n"
        "  name: demo\n"
        "spec:\n"
        "  target: llm\n"
        "  failure_mode: timeout\n"
    )

    result = runner.invoke(cli.app, ["apply", str(path), "--api-key", "k", "--timeout", "75"])

    assert result.exit_code == 0, result.output
    assert _FakeClient.last_kwargs["timeout"] == 75.0
