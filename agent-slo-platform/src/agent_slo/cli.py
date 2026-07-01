"""sloctl command-line interface."""

from __future__ import annotations

from pathlib import Path

import httpx
import typer

from agent_slo.yaml_spec import parse_yaml

app = typer.Typer(help="Agent SLO Platform CLI")

API_BASE = "http://localhost:8000"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


@app.command()
def apply(
    file: Path = typer.Argument(
        ..., help="Path to YAML file containing SLO/RiskBudget definitions"
    ),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Apply SLO/RiskBudget YAML definitions to the API."""
    content = file.read_text()
    docs = parse_yaml(content)
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))

    for doc in docs:
        meta = doc.metadata
        tenant_resp = client.get("/api/v1/tenants/me")
        if tenant_resp.status_code == 401:
            typer.echo("Invalid API key; tenant not found.", err=True)
            raise typer.Exit(1)

        # Ensure SLI exists or create placeholder
        sli_name = doc.spec.sli if doc.kind == "SLO" else "risk_budget"
        sli_resp = client.get("/api/v1/slis")
        slis = sli_resp.json()
        sli_id = next((s["id"] for s in slis if s["name"] == sli_name), None)
        if not sli_id:
            sli_payload = {
                "name": sli_name,
                "metric_type": "ratio" if doc.kind == "SLO" else "budget",
                "source": "otel_attribute" if doc.kind == "SLO" else "risk_weight",
                "config": {},
            }
            sli_resp = client.post("/api/v1/slis", json=sli_payload)
            sli_resp.raise_for_status()
            sli_id = sli_resp.json()["id"]

        if doc.kind == "SLO":
            payload = {
                "sli_id": sli_id,
                "name": meta.name,
                "target": doc.spec.target,
                "comparator": doc.spec.comparator,
                "window": doc.spec.window,
                "burn_rate_alert_thresholds": [
                    {"threshold": t.threshold, "severity": t.severity}
                    for t in doc.spec.burn_rate_alerts
                ],
                "labels": doc.spec.labels,
            }
            resp = client.post("/api/v1/slos", json=payload)
        else:
            payload = {
                "sli_id": sli_id,
                "name": meta.name,
                "target": 1.0,
                "comparator": "gt",
                "window": doc.spec.window,
                "risk_budget": {
                    "budget": doc.spec.budget,
                    "window": doc.spec.window,
                    "weights": doc.spec.weights,
                    "action": doc.spec.action,
                },
                "burn_rate_alert_thresholds": [
                    {"threshold": t.threshold, "severity": t.severity}
                    for t in doc.spec.burn_rate_alerts
                ],
            }
            resp = client.post("/api/v1/slos", json=payload)

        resp.raise_for_status()
        typer.echo(f"Applied {doc.kind} '{meta.name}' -> {resp.json()['id']}")


@app.command()
def status(
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Print current SLO status."""
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    resp = client.get("/api/v1/status")
    resp.raise_for_status()
    for entry in resp.json():
        icon = "✅" if not entry["is_breaching"] else "❌"
        typer.echo(
            f"{icon} {entry['slo_name']} ({entry['sli_name']}): "
            f"{entry['current_value']:.4f} vs target {entry['target']:.4f} "
            f"| budget {entry['budget_consumed']:.2%} | burn {entry['burn_rate']:.2f}"
        )


@app.command()
def report(
    standard: str = typer.Argument("owasp", help="Compliance standard: owasp"),
    api_key: str = typer.Option("dev-api-key", "--api-key", "-k"),
    base_url: str = typer.Option(API_BASE, "--base-url", "-u"),
) -> None:
    """Generate a compliance report."""
    client = httpx.Client(base_url=base_url, headers=_headers(api_key))
    if standard.lower() == "owasp":
        resp = client.get("/api/v1/compliance/owasp")
    else:
        resp = client.get(f"/api/v1/compliance/{standard.lower()}")
    resp.raise_for_status()
    typer.echo(resp.text)


if __name__ == "__main__":
    app()
