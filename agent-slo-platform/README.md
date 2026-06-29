# Agent SLO Platform

Service Level Objectives for AI agents. OpenTelemetry-native, multi-tenant, and compliance-aware.

## Quick Start

```bash
cp .env.example .env
docker compose up -d db
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
pytest
uvicorn agent_slo.api:app --reload
```

## Define an SLO

```yaml
# example-slo.yaml
apiVersion: agentops.io/v1
kind: SLO
metadata:
  name: task-success-rate
  tenant: acme-corp
  environment: production
spec:
  sli: task_success_rate
  target: 0.95
  comparator: gt
  window: 7d
  burnRateAlerts:
    - threshold: 0.02
      severity: info
    - threshold: 0.10
      severity: critical
```

Apply it:

```bash
sloctl apply -f example-slo.yaml
```

Send OpenTelemetry traces:

```bash
curl -X POST http://localhost:8000/v1/traces \
  -H "X-API-Key: dev-api-key" \
  -H "Content-Type: application/json" \
  -d @example-trace.json
```

Check status:

```bash
curl http://localhost:8000/api/v1/status?tenant=acme-corp
```

## Docs

- [Specification](SPEC.md)
- [Deployment Guide](docs/deployment.md)
- [Architecture](docs/architecture.md)

## License

MIT
