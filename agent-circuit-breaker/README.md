# Circuit Breaker

[![CI/CD](https://img.shields.io/github/actions/workflow/status/Anandhasasidharan/AgentOps-Agent-System-Operations/agentops.yml?branch=main&logo=github)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Tests](https://img.shields.io/badge/tests-36%20passing-6C5CE7?logo=pytest)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Coverage](https://img.shields.io/badge/coverage-75%25-22BA5A)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python)](https://python.org)

Runtime safety for AI agents. Intercepts tool calls, detects anomalies, enforces policies, and provides kill switch + rollback.

**Features:** DTMC prediction · PAC bounds · Graph monitoring · Z-score anomaly detection · Policy engine · Kill switch · Rollback engine

📖 [Full docs](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/circuit-breaker)

## Quick Start

```bash
docker compose up -d
```

Or locally:

```bash
pip install -e agentops-core/ && pip install -e agentops-events/ && pip install -e ".[dev]"
uvicorn circuit_breaker.api:app --port 8001 --reload
```

## Key Endpoints

| Endpoint | Description |
|---|---|
| `POST /v1/intercept` | Intercept a tool call (returns allow/block/kill) |
| `GET /api/v1/predict` | DTMC risk prediction |
| `GET /api/v1/graph/status` | Execution graph status |
| `GET /api/v1/graph/anomalies` | Graph anomalies |
| `POST /api/v1/policies` | Create a policy |
| `POST /api/v1/kill-switch/{id}/activate` | Activate kill switch |
| `POST /api/v1/incidents/{id}/rollback` | Execute rollback |

## Testing

```bash
python -m pytest -x --cov=circuit_breaker --cov-report=term-missing
```

## License

MIT
