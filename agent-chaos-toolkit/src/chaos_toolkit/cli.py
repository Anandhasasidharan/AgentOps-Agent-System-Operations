"""chaosctl command-line interface."""

from __future__ import annotations

from pathlib import Path

import httpx
import typer

from chaos_toolkit.scenarios import parse_scenario_yaml

app = typer.Typer(help="Agent Chaos Toolkit CLI")

API_BASE = "http://localhost:8002"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


@app.command()
def apply(
    file: Path = typer.Argument(..., help="Path to YAML file containing ChaosScenario definitions"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Apply chaos scenario YAML definitions to the API."""
    content = file.read_text()
    docs = parse_scenario_yaml(content)
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))

    for doc in docs:
        meta = doc.metadata
        spec = doc.spec
        payload = {
            "name": meta.name,
            "description": meta.description,
            "target_type": spec.target,
            "failure_mode": spec.failure_mode,
            "config": spec.config,
            "expected_behavior": spec.expected_behavior,
            "agent_should_survive": spec.agent_should_survive,
        }
        resp = client.post("/api/v1/scenarios", json=payload)
        resp.raise_for_status()
        typer.echo(f"Applied scenario '{meta.name}' -> {resp.json()['id']}")


@app.command()
def run(
    scenario_id: str = typer.Argument(..., help="Scenario UUID"),
    agent_id: str = typer.Argument(..., help="Agent ID to test"),
    tenant_id: str = typer.Option(..., "--tenant", "-t", help="Tenant UUID"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Run a single chaos experiment."""
    client = httpx.Client(base_url=base_url, headers=_headers(tenant_id))
    payload = {"scenario_id": scenario_id, "agent_id": agent_id}
    resp = client.post("/api/v1/experiments", json=payload)
    resp.raise_for_status()
    data = resp.json()
    score = data.get("resilience_score", 0)
    icon = "✅" if score and score >= 0.7 else "❌"
    typer.echo(f"{icon} Experiment {data['id']}: score={score}")


@app.command()
def batch(
    agent_id: str = typer.Argument(..., help="Agent ID to test"),
    tenant_id: str = typer.Option(..., "--tenant", "-t", help="Tenant UUID"),
    all_scenarios: bool = typer.Option(True, "--all/--select"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Run all chaos scenarios against an agent."""
    client = httpx.Client(base_url=base_url, headers=_headers(tenant_id))
    payload = {"agent_id": agent_id, "run_all_enabled": all_scenarios}
    resp = client.post("/api/v1/experiments/batch", json=payload)
    resp.raise_for_status()
    data = resp.json()
    typer.echo(f"Ran {len(data)} experiments")
    for exp in data:
        score = exp.get("resilience_score", 0)
        icon = "✅" if score and score >= 0.7 else "❌"
        typer.echo(f"  {icon} {exp['scenario_name']}: score={score:.2f}")


@app.command()
def report(
    tenant_id: str = typer.Option(..., "--tenant", "-t", help="Tenant UUID"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Show resilience score summary."""
    client = httpx.Client(base_url=base_url, headers=_headers(tenant_id))
    resp = client.get("/api/v1/resilience-score")
    resp.raise_for_status()
    data = resp.json()
    typer.echo(f"Total experiments: {data['total_experiments']}")
    typer.echo(f"Passed: {data['passed']}")
    typer.echo(f"Failed: {data['failed']}")
    typer.echo(f"Pass rate: {data['pass_rate']:.1%}")
    typer.echo(f"Average resilience score: {data['avg_resilience_score']:.2f}")
    if data.get("worst_performing_target"):
        typer.echo(f"Worst target: {data['worst_performing_target']}")
    for rec in data.get("recommendations", []):
        typer.echo(f"  - {rec}")


@app.command()
def seed(
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Seed built-in chaos scenarios."""
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.post("/api/v1/scenarios/seed")
    resp.raise_for_status()
    data = resp.json()
    typer.echo(f"Seeded {len(data)} built-in scenarios")


if __name__ == "__main__":
    app()
