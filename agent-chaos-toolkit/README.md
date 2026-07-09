# Chaos Toolkit

[![CI/CD](https://img.shields.io/github/actions/workflow/status/Anandhasasidharan/AgentOps-Agent-System-Operations/agentops.yml?branch=main&logo=github)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Tests](https://img.shields.io/badge/tests-30%20passing-6C5CE7?logo=pytest)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Coverage](https://img.shields.io/badge/coverage-70%25-22BA5A)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python)](https://python.org)

Resilience testing for AI agents. Inject faults into LLMs, tools, RAG, and MCP servers — then score how well your agent survives.

**Features:** 16 failure modes · 15 built-in scenarios · LLM scenario proposer · Closed-loop refinement · CI/CD integration

📖 [Full docs](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/chaos-toolkit)

## Quick Start

```bash
pip install -e agentops-core/ && pip install -e ."[dev]"
uvicorn chaos_toolkit.api:app --port 8002 --reload
```

## Seed & Run

```bash
chaosctl seed --api-key <tenant-uuid>
chaosctl run <scenario-id> <agent-id> --tenant <uuid>
chaosctl report --tenant <uuid>
```

## Key Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/v1/experiments` | Run a chaos experiment |
| `POST /api/v1/scenarios/propose` | LLM-generate new scenarios |
| `POST /api/v1/scenarios/refine` | Refine proposed scenarios |
| `GET /api/v1/resilience-score` | Aggregated resilience report |
| `GET /api/v1/reports/{id}/junit` | JUnit XML |

## Testing

```bash
python -m pytest -x --cov=chaos_toolkit --cov-report=term-missing
```

## License

MIT
