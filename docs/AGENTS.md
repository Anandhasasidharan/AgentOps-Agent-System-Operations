# AgentOps: AGENTS.md

Context for any coding agent working in this repo. Read it fully before changing anything. Commands and facts here were checked against `main` at `bff4c4c` on 2026-10-23 unless a line says otherwise. If something here is wrong, fix this file in the same PR.

## What this is

AgentOps is a safety and observability platform for tool-calling AI agents. Every tool call goes to the Circuit Breaker first, which decides allow, block, kill, or alert before the tool runs. Around it sit chaos testing, SLO evaluation, a dashboard, and an event gateway. Python 3.11, FastAPI, SQLAlchemy async, PostgreSQL, NATS, OpenTelemetry.

The Circuit Breaker is the product. The other services support it.

## Current mission

Follow `docs/ROADMAP.md`, `docs/PLAN.md`, and `docs/FEATURES.md`. The project's problem is verification, not missing features.

- Work on **one milestone at a time**, in order: M0, M1, M2, M3, M4, R1, M5, M6, R2.
- **Do not add new features** until M1 ("make the claims true") is done.
- If a task is not in the current milestone, record it in `docs/FOLLOWUPS.md` and move on.

## Rules for agents (non-negotiable)

1. **Evidence over claims.** Run the command, paste the real output. Never write "all tests pass", "CI green", or a test count you did not just observe. A past session reported "90 tests passing, CI all green" without running anything while the repo was broken.
2. **Never edit an existing test to make it pass.** If current behavior looks like a bug, keep the test, write it up in `docs/DEVIATIONS.md`, and continue.
3. **Fail closed.** Anything on the safety path (adapters, SDK, intercept) denies on error unless `AGENTOPS_FAIL_MODE=open` is set explicitly. Every degraded decision logs a structured event.
4. **No claim without a test, endpoint, or benchmark.** Do not add README text for a feature that `curl` cannot reach.
5. **Small commits, one per step,** conventional messages (`fix:`, `feat:`, `test:`, `ci:`, `docs:`). Work on a branch named `feat/m<N>-<name>`. Never push to `main`, never force-push.
6. **No secrets in the repo.** No real keys in compose files, docs, or tests.
7. **Stay in scope.** Smallest diff that satisfies the task.
8. **Update `docs/FEATURES.md`** rows touched by your change, in the same PR.
9. If a requirement is ambiguous, pick the safer option, record it in `docs/DECISIONS.md`, and continue.

## Repo map

Each package has a `src/` layout and its own `tests/` inside the package directory.

| Package | Role | Port |
|---|---|---|
| `agent-circuit-breaker` | Intercept, policy, risk, anomaly, DTMC, graph, kill switch, rollback, incidents | 8001 |
| `agent-chaos-toolkit` | Failure injection, scenarios, resilience scoring, LLM scenario proposer | 8002 |
| `agent-slo-platform` | OTLP ingestion, SLIs, SLOs, burn rate, alerts, compliance mapping | 8000 |
| `dashboard` | Server-rendered health page | 8003 |
| `agent-gateway` | NATS to WebSocket bridge | 8004 |
| `agentops-core` | Shared base models, auth, rate limiter, telemetry | n/a |
| `agentops-events` | Event models, 6 NATS topics, `publish_event()` | n/a |
| `agentops-sdk` | Python client | n/a |
| `agentops-langchain` | LangChain wrapper and callback handler | n/a |
| `agentops-engine` | Native C policy engine plus Python reference engine (optional until M5) | n/a |

Other directories: `monitoring/` (Prometheus, Grafana), `scripts/` (`seed.py`, `demo_langchain.py`), `website/` (Docusaurus), `docs/`. A single root `Dockerfile` builds every image through `ARG SERVICE`. The root `pyproject.toml` holds tool config only.

## Setup

Install order matters: `agentops-core`, then `agentops-events`, then everything else. `agentops-events` is not on PyPI.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e agentops-core/ -e agentops-events/
pip install -e agent-circuit-breaker/"[dev]" -e agent-chaos-toolkit/"[dev]" -e agent-slo-platform/"[dev]"
pip install -e dashboard/"[dev]" -e agent-gateway/"[dev]" -e agentops-sdk/"[dev]" -e agentops-langchain/"[dev]"
```

Dependencies pin `sqlalchemy[asyncio]>=2.0,<2.2`, which installs `greenlet`. The native engine is optional until M5; install `agentops-engine` after `agent-circuit-breaker` only if you are working on it.

`make setup` installs all 9 Python packages. `make test` runs all 9 suites. `make test-engine` runs the engine tests (requires `agent-circuit-breaker` and `agentops-engine` installed).

## Commands

| Task | Command |
|---|---|
| Run everything | `docker compose up --build` (`make dev`) |
| Seed demo data | `python scripts/seed.py` (`make demo`) |
| Test one package | `cd <package> && python -m pytest -x` |
| Lint | `make lint` (pinned `ruff==0.16.10`) |
| Format check | `make format-check` (pinned `black==26.10.0`) |

## Testing facts

- All tests use in-memory SQLite (`aiosqlite:///:memory:`). No Postgres needed locally.
- Coverage thresholds: Circuit Breaker 75%, Chaos 70%, SLO 80%, set in each package's `pyproject.toml`.
- `asyncio_mode = "auto"`.
- `respx` mocks HTTP in the SDK and LangChain tests.
- NATS is mocked with `patch.object(nc_module, "HAS_NATS", True)` and `patch.object(nc_module, "_nats", MagicMock())`.
- CI matrix covers every package: core, events, circuit-breaker, chaos, slo, dashboard, gateway, sdk, langchain, and engine. A `clean-install` job creates a new venv and runs all suites.
- Last observed locally on 2026-10-23: Core 10, Events 11, Circuit Breaker 88 (81.6%), Chaos 63 (82.9%), SLO 36 (80.4%), Dashboard 1, Gateway 8, SDK 11, LangChain 10, Engine 7. Re-run before quoting numbers.

## Traps and quirks

- **Conditions are typed.** `circuit_breaker.policy_conditions` validates one model per policy type for both the API and `cbctl apply`; unknown keys are a 422. `agent_id` is an optional common condition that scopes a policy to one agent. Cross-midnight time windows are rejected.
- **Topic constants** import from the package root: `from agentops_events import TOPIC_CB_INCIDENT`, not from `models`.
- **NATS is optional.** With `nats-py` missing or `NATS_URL` unset, a no-op publisher runs. Publishing is fire-and-forget.
- **`create_all` runs at startup** in all three DB-owning services. Alembic exists only in the SLO Platform. Do not change schemas casually; migrations are M6.2.
- **One shared Postgres** for all services. Table names are disjoint today. Keep them that way.
- **Rate limiter is in memory,** per tenant, 60 s window, `RATE_LIMIT_RPM` (default 60, `0` disables, `/health` and `/metrics` bypass). Single replica only. `RATE_LIMIT_RPM=0` is covered by a regression test.
- **Auth:** `X-API-Key: slug:random-hex`, split on `:`, SHA-256 hash in `Tenant.api_key_hash`, key shown once. The gateway validates through the SLO service's `/api/v1/tenants/me`. Gateway auth is currently optional: omitting the key lets you in.
- **Fail closed by default:** the SDK and LangChain adapter deny when the breaker is unreachable, returns non-2xx, or returns a malformed verdict. `AGENTOPS_FAIL_MODE=open` is the explicit override. Every degraded decision logs `agentops.degraded_decision`.
- **Chaos injection sleeps** 25 to 120 seconds inside a request for some modes. Do not run it in a request path you care about.
- **`/health`** returns `{"status":"ok"}` without probing the database or NATS.
- **Pydantic v2:** use `model_dump_json()`, not `.json()`.
- Dashboard `api.py` has a per-file E501 ignore because of embedded CSS and JS.

## Architecture

```
Agent -> adapter or SDK -> POST /v1/intercept (Circuit Breaker)
                              |-> policy engine (priority desc, first match wins)
                              |-> risk score, anomaly, DTMC, graph monitor
                              |-> kill switch, incident, rollback record
                              |-> publish event (NATS) + OTLP span
SLO Platform <- OTLP spans        breach event -> agent-scoped auto-lockdown policy -> blocked call
NATS -> Gateway -> WebSocket -> Dashboard
Prometheus scrapes /metrics on all services
```

OTel emission is a fire-and-forget HTTP POST of OTLP JSON.

## Native engine (when working in `agentops-engine`)

Plan: a C library (`libagentops`) for policy evaluation, called from Python through cffi. Python remains the fallback and the test oracle. Selection via `AGENTOPS_ENGINE=py|c|auto` (default `py` until parity is proven).

- C11, no dependencies beyond libc and pthreads. Compile with `-Wall -Wextra -Werror`.
- Time is passed in by the caller. C never reads a clock.
- Integer arithmetic only for policy evaluation, so C and Python can match exactly.
- No heap allocation inside `ao_intercept`. Pools are sized at engine creation. On exhaustion, fail closed with a defined reason code.
- Never abort or exit. Every error is a status code.
- Treat policy blobs as hostile: check every length, offset, and checksum with overflow-safe arithmetic.
- Every change needs differential tests (Python versus C, identical verdicts), plus ASan and UBSan. Parser changes need fuzzing.
- The native engine is about 2% of a server request by the audit's numbers (unverified). Its purpose is embedded in-process mode. Do not claim server-path speedups without a benchmark.

## Definition of done for any task

1. The tests you added fail without your change and pass with it.
2. The full suite for every package you touched passes, with real output pasted.
3. Lint and format pass at the pinned versions.
4. `docs/FEATURES.md` rows updated.
5. No unrelated changes, no secrets, no commented-out code.
6. Anything you were unsure about is written down as a question, not guessed.

## Report format

End every task with: branch and commit list, each acceptance command with its **actual** output, a PASS or FAIL table (unfinished means FAIL), and any deviations or open questions.

## Documents

| File | Purpose |
|---|---|
| `docs/ROADMAP.md` | What and why, milestones, gates |
| `docs/PLAN.md` | Tasks, estimates, acceptance evidence, working loop |
| `docs/FEATURES.md` | Honest per-feature status |
| `docs/DECISIONS.md` | Choices and tradeoffs (create when first needed) |
| `docs/DEVIATIONS.md` | Existing behavior that looks wrong but was preserved |
| `docs/FOLLOWUPS.md` | Out-of-scope findings |
| `docs/BENCHMARKS.md` | Published measurements with method (M4) |

## Not building

An LLM or inference gateway, eval and dataset tooling, a general APM backend, a hosted multi-tenant SaaS, a custom agent framework, mechanistic interpretability. Export to existing tools instead.
