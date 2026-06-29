# Agent Circuit Breaker

Runtime safety for AI agents. Intercepts tool calls, detects anomalies, enforces policies, and provides kill switch + rollback.

## Quick Start

```bash
docker compose up -d
```

Or locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn circuit_breaker.api:app --port 8001 --reload
```

## Intercept a Tool Call

```bash
curl -X POST http://localhost:8001/v1/intercept \
  -H "X-Tenant-ID: <tenant-uuid>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "onboarding-agent",
    "tool_name": "delete_file",
    "tool_input": {"path": "/data/users.csv"},
    "duration_ms": 150
  }'
```

## Define a Policy

```yaml
# policy.yaml
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: block-destructive-tools
spec:
  type: tool_blocklist
  priority: 10
  conditions:
    tools:
      - delete_file
      - execute_command
      - drop_table
  action:
    action: kill
```

Apply it:

```bash
cbctl apply -f policy.yaml --tenant <uuid>
```

## Key Endpoints

| Endpoint | Description |
|---|---|
| `POST /v1/intercept` | Intercept a tool call (returns allow/block/kill) |
| `POST /api/v1/policies` | Create a policy |
| `GET /api/v1/policies` | List policies |
| `POST /api/v1/kill-switch/{id}/activate` | Activate kill switch for an agent |
| `POST /api/v1/kill-switch/{id}/release` | Release kill switch |
| `GET /api/v1/agents/{id}/status` | Get agent status |
| `POST /api/v1/incidents/{id}/rollback` | Execute rollback for an incident |

## License

MIT
