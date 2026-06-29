# Agent Chaos Toolkit

Resilience testing for AI agents. Inject faults into LLMs, tools, RAG, and MCP servers — then score how well your agent survives.

## Quick Start

```bash
pip install -e ".[dev]"
uvicorn chaos_toolkit.api:app --port 8002 --reload
```

## Seed Built-in Scenarios

```bash
chaosctl seed --api-key <tenant-uuid>
```

15 scenarios across 4 targets: LLM (timeout, hallucination, refusal, model downgrade), Tool (timeout, crash, bad output, wrong data), RAG (no results, bad data, corrupted context, slow response), MCP (server down, timeout, bad capabilities, auth failure).

## Run an Experiment

```bash
chaosctl run <scenario-id> <agent-id> --tenant <uuid>
```

Or via API:

```bash
curl -X POST http://localhost:8002/api/v1/experiments \
  -H "X-API-Key: <tenant-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "<id>", "agent_id": "onboarding-agent"}'
```

## Run All Scenarios

```bash
chaosctl batch my-agent --tenant <uuid> --all
```

## View Resilience Score

```bash
chaosctl report --tenant <uuid>
```

## CI Integration

Generate a JUnit XML report:

```bash
curl http://localhost:8002/api/v1/reports/<id>/junit -H "X-API-Key: <uuid>"
```

## Architecture

```
Test Agent → Chaos Injector → Target (LLM/Tool/RAG/MCP) → Scoring Engine → Report
```

## License

MIT
