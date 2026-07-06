# AgentOps — AGENTS.md

## Install order (must)
agentops-core -> agentops-events -> service:
```bash
pip install -e agentops-core/
pip install -e agentops-events/
pip install -e agent-circuit-breaker/"[dev]"
```
`make setup` does this for all 9 packages. CI does the same.

## Commands
| Task | Command |
|------|---------|
| Run everything | `docker compose up --build` (`make dev`) |
| Seed demo | `make demo` (or `python scripts/seed.py`) |
| Test one service | `cd agent-circuit-breaker && python -m pytest -x` |
| Test all | `make test` |
| Lint | `ruff check agent-circuit-breaker/src agent-chaos-toolkit/src agent-slo-platform/src dashboard/src agent-gateway/src agentops-events/src agentops-sdk/src` |
| Format check | `black --check <same paths>` |

## Repo structure
- **9 packages**, each in its own dir, all use `src/` layout
- Each has `tests/` inside its package dir (root `tests/` is empty, ignore it)
- Single `Dockerfile` at root builds all images via `ARG SERVICE`
- Root `pyproject.toml` has no packages of its own — just tool config

## Testing quirks
- All tests use **SQLite in-memory** (`aiosqlite:///:memory:`) — no Postgres needed locally
- Coverage thresholds vary: CB 75%, Chaos 70%, SLO 80% (set in each package's `pyproject.toml` `addopts`)
- Agent's loop scope: `asyncio_mode = "auto"` at root + each service
- `respx` used for HTTP mocking in agentops-sdk and agentops-langchain tests

## Auth
- API key format: `slug:random-hex-token` (e.g. `acme-corp:a1b2c3...`)
- Sent as `X-API-Key` header, parsed by splitting on `:`
- Hash stored in `Tenant.api_key_hash`; key returned once on creation
- Gateway validates keys by calling SLO's `/api/v1/tenants/me`
- Dashboard passes `API_KEY` env var to gateway WebSocket as `?api_key=` query param

## Events & NATS
- `agentops-events` package: event models, 6 NATS topics, `publish_event()` with retry
- Topic constants must be imported from package root (`from agentops_events import TOPIC_CB_INCIDENT`), not from `models` submodule
- NATS is optional — services work with no-op publisher when `nats-py` not installed or `NATS_URL` unset
- Tests mock NATS via `patch.object(nc_module, "HAS_NATS", True)` + `patch.object(nc_module, "_nats", MagicMock())`

## Style
- ruff: line-length=100, select E/F/I/W. Dashboard `api.py` has per-file E501 ignore (embedded CSS/JS)
- black: line-length=100, target py311
- Pydantic v2: use `model_dump_json()`, not `.json()`

## CI/CD pipeline
`.github/workflows/agentops.yml`:
1. **test** (5-matrix) → `pytest -x --cov=... --cov-report=term-missing`
2. **lint** → ruff + black --check
3. **build** → Docker Buildx (5 images) — conditional on secrets
4. **deploy-infra** → Terraform — conditional
5. **deploy-app** → Helm — conditional
6. **smoke** → Python SDK health check — conditional

## Architecture notes
- All services share one Postgres DB, no per-service databases
- Gateway (port 8004) bridges NATS→WebSocket for real-time dashboard
- Prometheus scrapes all 5 services on `/metrics` (ports 8000-8004)
- OTel emission is fire-and-forget HTTP POST with OTLP JSON format
