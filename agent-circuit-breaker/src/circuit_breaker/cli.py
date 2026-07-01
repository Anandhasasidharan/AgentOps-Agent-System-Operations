"""cbctl command-line interface for Agent Circuit Breaker."""

from __future__ import annotations

from pathlib import Path

import httpx
import typer

from circuit_breaker.yaml_policy import parse_yaml

app = typer.Typer(help="Agent Circuit Breaker CLI")

API_BASE = "http://localhost:8001"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


@app.command()
def apply(
    file: Path = typer.Argument(..., help="Path to YAML file containing Policy definitions"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k", help="API key (tenant slug)"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    content = file.read_text()
    docs = parse_yaml(content)
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))

    for doc in docs:
        meta = doc.metadata
        spec = doc.spec
        payload = {
            "name": meta.get("name", f"policy-{spec.policy_type}"),
            "description": meta.get("description", ""),
            "enabled": spec.enabled,
            "priority": spec.priority,
            "policy_type": spec.policy_type,
            "conditions": spec.conditions,
            "action": spec.action.action,
            "action_config": spec.action.config,
        }
        resp = client.post("/api/v1/policies", json=payload)
        resp.raise_for_status()
        typer.echo(f"Applied Policy '{payload['name']}' -> {resp.json()['id']}")


@app.command()
def status(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k", help="API key (tenant slug)"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.get(f"/api/v1/agents/{agent_id}/status")
    resp.raise_for_status()
    data = resp.json()

    status_icon = "🔴" if data["is_killed"] else "🟢"
    typer.echo(f"{status_icon} Agent: {data['agent_id']}")
    typer.echo(f"  Killed: {data['is_killed']}")
    typer.echo(f"  Active incidents: {len(data['active_incidents'])}")
    typer.echo(f"  Recent decisions:")
    for d in data["recent_decisions"][:5]:
        icon = "❌" if d["blocked"] else "✅"
        typer.echo(f"    {icon} {d['tool_name']} -> {d['decision']}")


@app.command()
def policies(
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k", help="API key (tenant slug)"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.get("/api/v1/policies")
    resp.raise_for_status()
    for p in resp.json():
        icon = "✅" if p["enabled"] else "⏸️"
        typer.echo(f"{icon} {p['name']} ({p['policy_type']}) -> {p['action']} [priority {p['priority']}]")


@app.command()
def kill(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    reason: str = typer.Option("Manual kill", "--reason", "-r"),
    ttl: int = typer.Option(3600, "--ttl", help="TTL in seconds"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k", help="API key (tenant slug)"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.post(f"/api/v1/kill-switch/{agent_id}/activate?reason={reason}&ttl={ttl}")
    resp.raise_for_status()
    typer.echo(f"Kill switch activated for {agent_id}: {reason}")


@app.command()
def release(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k", help="API key (tenant slug)"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.post(f"/api/v1/kill-switch/{agent_id}/release")
    resp.raise_for_status()
    typer.echo(f"Kill switch released for {agent_id}")


if __name__ == "__main__":
    app()
