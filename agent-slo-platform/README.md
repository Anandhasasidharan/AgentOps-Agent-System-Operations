# SLO Platform

[![CI/CD](https://img.shields.io/github/actions/workflow/status/Anandhasasidharan/AgentOps-Agent-System-Operations/agentops.yml?branch=main&logo=github)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Tests](https://img.shields.io/badge/tests-24%20passing-6C5CE7?logo=pytest)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Coverage](https://img.shields.io/badge/coverage-80%25-22BA5A)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python)](https://python.org)

Service Level Objectives for AI agents. OpenTelemetry-native, multi-tenant, and compliance-aware.

**Features:** OTel ingestion · GenAI semantic conventions · Trust score integration · SLO evaluation · Burn-rate math · OWASP/EU AI Act

📖 [Full docs](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/slo-platform)

## Quick Start

```bash
pip install -e agentops-core/ && pip install -e ."[dev]"
uvicorn agent_slo.api:app --port 8000 --reload
```

## Define an SLO

```yaml
apiVersion: agentops.io/v1
kind: SLO
metadata:
  name: task-success-rate
spec:
  sli: task_success_rate
  target: 0.95
  comparator: gt
  window: 7d
  burnRateAlerts:
    - threshold: 0.02
      severity: info
```

Apply it: `sloctl apply -f slo.yaml`

## Key Endpoints

| Endpoint | Description |
|---|---|
| `POST /v1/traces` | Ingest OTel spans |
| `GET /api/v1/status` | SLO dashboard |
| `GET /api/v1/compliance/owasp` | OWASP report |
| `GET /api/v1/compliance/eu-ai-act` | EU AI Act evidence |

## Testing

```bash
python -m pytest -x --cov=agent_slo --cov-report=term-missing
```

## License

MIT
