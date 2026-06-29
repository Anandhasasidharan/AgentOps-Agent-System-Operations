# AgentOps — Agent System Operations Platform

Three microservices for operating AI agents safely, reliably, and at scale.

| Service | Port | DB | Purpose |
|---------|------|----|---------|
| **Agent Circuit Breaker** | 8001 | PostgreSQL | Real-time safety guard for agent tool calls |
| **Agent Chaos Toolkit** | 8002 | SQLite | Pre-production resilience testing via fault injection |
| **Agent SLO Platform** | 8000 | PostgreSQL | Continuous observability, SLO evaluation, compliance |

---

## 1. Agent Circuit Breaker (port 8001)

### Purpose

A real-time safety proxy that intercepts every tool call an agent makes and decides whether to **allow**, **block**, **kill**, or **alert** — before the tool executes. Prevents catastrophic agent actions (deleting production data, running shell commands, spending API budget) before they happen.

### How It Works

The circuit breaker exposes a single intercept endpoint (`POST /v1/intercept`). Any agent framework sends tool calls through it:

```
Agent Tool Call
      │
      ▼
┌─────────────────────────────────────────────────┐
│  INTERCEPT PIPELINE                              │
│                                                  │
│  1. Kill Switch Check ── killed? → block +      │
│                          create incident         │
│                                                  │
│  2. Risk Scoring ──── composite score:           │
│     tool_weight × 40% +                           │
│     input_risk × 30% +                            │
│     failure_rate × 15% +                          │
│     cost_rate × 15%                               │
│                                                  │
│  3. Anomaly Detection ── composite score:         │
│     frequency_Z_score × 30% +                     │
│     tool_entropy × 25% +                          │
│     reasoning_loop × 30% +                        │
│     timing_Z_score × 15%                          │
│                                                  │
│  4. Policy Evaluation ── 8 policy types           │
│     (allowlist, blocklist, rate_limit, etc.)      │
│                                                  │
│  5. State Update ── 5-minute windowed counters    │
│                                                  │
│  6. Return decision                               │
│     {allowed: bool, decision: str, ...}           │
└─────────────────────────────────────────────────┘
```

### Key Algorithms

**Risk Scoring** — weighted composite of four factors:
- **Tool weight**: built-in weights for 16 common tool patterns (delete_file=0.95, bash=0.95, execute_sql=0.90, send_http_request=0.50)
- **Input risk**: pattern-matches tool parameters against 14 dangerous patterns (`DELETE FROM`, `rm -rf`, `eval(`, base64 encoded strings)
- **Failure rate**: recent failure history for this agent/tool combination
- **Cost rate**: token/cost spend rate to prevent budget blowout

**Anomaly Detection** — four independent detectors, combined into a single score:
- **Frequency Z-score**: how many standard deviations from the agent's normal call frequency
- **Entropy drift**: Shannon entropy of the tool distribution — a sudden shift to a narrow set of tools signals behavioral change
- **Reasoning loop**: consecutive identical tool calls indicate an agent stuck in a loop
- **Timing Z-score**: unusually fast or slow call durations

**Policy Engine** — priority-ordered evaluation supporting 8 policy types:

| Type | Description |
|------|-------------|
| `tool_allowlist` | Only allow specified tools |
| `tool_blocklist` | Block specified tools |
| `rate_limit` | Max calls per time window |
| `token_budget` | Max token spend per window |
| `risk_threshold` | Block if risk score > N |
| `anomaly_threshold` | Block if anomaly score > N |
| `time_window` | Only allow during certain hours |
| `reasoning_loop` | Block if N consecutive same-tool calls |

### Rollback Engine

When an incident is created, rollback can compensate for the action:

- **Inverse tool map**: `create_file` → `delete_file`, `write_file` → `restore_from_backup`, `process_payment` → `issue_refund`, etc.
- **State restore**: resets the agent's state counters
- **Cost refund**: logs the cost compensation

### API Endpoints (14)

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/v1/intercept` | **Core** — intercept a tool call |
| `POST` | `/api/v1/policies` | Create a policy |
| `GET` | `/api/v1/policies` | List policies |
| `GET` | `/api/v1/policies/{id}` | Get policy |
| `DELETE` | `/api/v1/policies/{id}` | Delete policy |
| `GET` | `/api/v1/tool-calls` | List tool call history |
| `POST` | `/api/v1/kill-switch/{agent}/activate` | Kill an agent |
| `POST` | `/api/v1/kill-switch/{agent}/release` | Release kill |
| `GET` | `/api/v1/kill-switch/{agent}` | Kill switch status |
| `GET` | `/api/v1/incidents` | List active incidents |
| `POST` | `/api/v1/incidents/{id}/resolve` | Resolve incident |
| `POST` | `/api/v1/incidents/{id}/rollback` | Execute rollback |
| `GET` | `/api/v1/agents/{id}/status` | Full agent status |

### CLI (`cbctl`)

```
cbctl apply <file>     Apply YAML policy definitions
cbctl status <agent>   Show agent status (killed, incidents, decisions)
cbctl policies         List all policies
cbctl kill <agent>     Activate kill switch
cbctl release <agent>  Release kill switch
```

### Data Models (6 tables)

- **Policy** — tenant-scoped rules with type, conditions (JSON), action
- **ToolCall** — record of every intercepted call with scores and decision
- **AgentState** — 5-minute windowed counters (call count, tokens, cost, failure rate, entropy)
- **Incident** — security/safety events with severity, category, rollback linkage
- **RollbackLog** — compensation action audit trail
- **KillSwitch** — TTL-based agent kill with trigger info

---

## 2. Agent Chaos Toolkit (port 8002)

### Purpose

A pre-production testing tool that injects controlled failures into agent systems to measure resilience. Models what happens when the LLM times out, a tool crashes, RAG returns garbage, or an MCP server goes down. Produces resilience scores and CI-friendly reports.

### How It Works

```
POST /api/v1/experiments
        │
        ▼
┌────────────────────────────────────────┐
│  run_experiment(scenario, agent_id)    │
│                                        │
│  1. Load scenario from DB              │
│     (or seed 15 built-in scenarios)    │
│                                        │
│  2. Lookup target injector             │
│     TARGET_INJECTORS = {               │
│       llm, tool, rag, mcp              │
│     }                                  │
│                                        │
│  3. Create Experiment record           │
│     status = "running"                 │
│                                        │
│  4. Call injector(config)              │
│     → simulated failure (no real API)  │
│                                        │
│  5. Log FaultLog                       │
│                                        │
│  6. Evaluate result:                   │
│     survived + behavior match  → 1.0  │
│     survived only               → 0.7  │
│     agent errored               → 0.2  │
│     injection failed            → 0.0  │
│                                        │
│  7. Return Experiment                  │
└────────────────────────────────────────┘
```

### Target Injectors (4 targets × 4 failure modes = 16 fault types)

| Target | Failure Modes | What It Simulates |
|--------|---------------|-------------------|
| **LLM** | timeout, hallucination, model_downgrade, refusal | AI model produces bad output or fails |
| **Tools** | timeout, crash (500), bad_output, wrong_data | External API returns errors or junk |
| **RAG** | no_results, bad_data, corrupted_context, slow_response | Knowledge retrieval fails |
| **MCP** | server_down (502), timeout, bad_capabilities, auth_failure (401) | MCP infrastructure fails |

All injectors are **synthetic** — no real LLM API calls, no real external services. The simulation runs purely in-process.

### 15 Built-in Scenarios

| # | Scenario | Target | Failure Mode | Agent Should Survive |
|---|----------|--------|--------------|---------------------|
| 1 | LLM Timeout During Reasoning | llm | timeout | Yes |
| 2 | LLM Hallucination in Tool Selection | llm | hallucination | Yes |
| 3 | LLM Model Downgrade | llm | model_downgrade | Yes |
| 4 | LLM Refusal to Execute | llm | refusal | Yes |
| 5 | Tool Timeout | tool | timeout | Yes |
| 6 | Tool Crash on Execution | tool | crash | Yes |
| 7 | Tool Returns Bad Output | tool | bad_output | Yes |
| 8 | Tool Returns Wrong Data | tool | wrong_data | Yes |
| 9 | RAG Returns No Results | rag | no_results | Yes |
| 10 | RAG Returns Corrupted Data | rag | bad_data | Yes |
| 11 | RAG Context Window Corruption | rag | corrupted_context | Yes |
| 12 | RAG Slow Response | rag | slow_response | Yes |
| 13 | MCP Server Down | mcp | server_down | Yes |
| 14 | MCP Timeout | mcp | timeout | Yes |
| 15 | MCP Authentication Failure | mcp | auth_failure | Yes |

### Scoring & Recommendations

**Per-experiment score**: 0.0–1.0 based on whether the agent survived and behavior matched expectations.

**Aggregate resilience score** across all experiments:
- Pass rate (score ≥ 0.7)
- Average resilience score
- Worst-performing target type
- Automated recommendations:

| Pass Rate | Recommendation |
|-----------|---------------|
| < 50% | **Critical** — "Implement fallback logic for [target]" |
| < 70% | **Warning** — "Add timeout handling with retry mechanism" |
| < 90% | **Info** — "Consider graceful degradation patterns" |

### CI/CD Integration

- **JUnit XML**: standard CI tool output (Jenkins, GitLab, CircleCI)
- **GitHub Actions summary**: Markdown table for step summaries

### API Endpoints (14)

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/scenarios` | Create scenario |
| `GET` | `/api/v1/scenarios` | List scenarios |
| `GET` | `/api/v1/scenarios/{id}` | Get scenario |
| `POST` | `/api/v1/scenarios/seed` | Seed 15 built-in scenarios |
| `POST` | `/api/v1/experiments` | **Core** — run a chaos experiment |
| `POST` | `/api/v1/experiments/batch` | Run all scenarios |
| `GET` | `/api/v1/experiments` | List experiments |
| `GET` | `/api/v1/experiments/{id}` | Get experiment |
| `GET` | `/api/v1/resilience-score` | Aggregated resilience report |
| `POST` | `/api/v1/reports` | Create CI report |
| `GET` | `/api/v1/reports` | List reports |
| `GET` | `/api/v1/reports/{id}/junit` | JUnit XML |
| `GET` | `/api/v1/reports/{id}/github-summary` | GitHub Actions summary |

### CLI (`chaosctl`)

```
chaosctl apply <file>        Apply YAML scenario definitions
chaosctl run <id> <agent>    Run single experiment
chaosctl batch <agent>       Run all scenarios against agent
chaosctl report              Show resilience score summary
chaosctl seed                Seed built-in scenarios
```

### Data Models (4 tables)

- **Scenario** — test definition (target, failure_mode, config JSON, expected_behavior)
- **Experiment** — test run record with status, injection details, resilience score
- **ExperimentReport** — aggregated report for CI/CD output
- **FaultLog** — per-call audit of injected faults and agent responses

---

## 3. Agent SLO Platform (port 8000)

### Purpose

Continuous observability and SLA/SLO management for AI agent systems. Ingests OpenTelemetry traces from agent runs, derives SLI metrics (success rate, latency, token usage, hallucination rate, tool accuracy), evaluates SLO targets, tracks error budgets, fires burn-rate alerts, and generates compliance reports (OWASP, EU AI Act).

### How It Works

```
OTel Spans (JSON via POST /v1/traces)
        │
        ▼
┌──────────────────────────────────────────┐
│  ingest_traces()                          │
│                                          │
│  1. parse_otlp_spans()                   │
│     → convert OTLP JSON to OtelSpan      │
│                                          │
│  2. resolve/create Agent                 │
│     by (tenant, environment, name)       │
│                                          │
│  3. _derive_metrics()                    │
│     for each span:                       │
│       task_success_ratio                 │
│       hallucination_rate                 │
│       tool_accuracy                      │
│       latency_p99                       │
│       token_usage                       │
│       cost_per_task                     │
│       steps_to_completion               │
│                                          │
│  4. Return ingest summary                │
└──────────────────────────────────────────┘

            ▼ (on status request)

┌──────────────────────────────────────────┐
│  evaluate_all_slos()                      │
│                                          │
│  for each SLO:                           │
│    1. aggregate_sli()                    │
│       → weighted avg or p99              │
│                                          │
│    2. evaluate_slo()                     │
│       → compare value to target          │
│                                          │
│    3. error_budget math                  │
│       consumed = target - value          │
│       remaining = total - consumed       │
│                                          │
│    4. compute_burn_rate()                │
│       burn = consumed / elapsed_ratio    │
│                                          │
│    5. evaluate_alerts()                  │
│       → fire if burn > threshold         │
│       → resolve if burn < threshold      │
│                                          │
│  6. Return status dashboard              │
└──────────────────────────────────────────┘
```

### SLI Types (7 derived from spans)

| SLI | Method | Description |
|-----|--------|-------------|
| `task_success_rate` | Weighted avg | Ratio of successful task completions |
| `hallucination_rate` | Weighted avg | Ratio of detected hallucination spans |
| `tool_accuracy` | Weighted avg | Ratio of correct tool selections |
| `cost_per_task` | Simple avg | Average cost per completed task |
| `steps_to_completion` | Simple avg | Average number of steps to finish task |
| `latency_p99` | Percentile | 99th percentile response latency |
| `token_usage` | Simple avg | Average token consumption per task |

### SLO Evaluation

Each SLO defines:
- **Target**: the desired metric value (e.g., `0.99` for 99% success rate)
- **Comparator**: `gt` (greater than target), `lt` (less than target), `eq` (equals target)
- **Window**: the evaluation window (e.g., `7d`, `24h`)
- **Burn rate thresholds**: alert when burn rate exceeds N (e.g., `[1.0, 5.0, 10.0]`)

**Error budget**: `total = 1 - target`. Burn rate = consumed / elapsed_window_ratio.

### Risk Budget

Per-SLO configurable risk weights per tool pattern. Consumed budget tracks cumulative risk spend, with threshold-based actions (warn, block) when exceeded.

### Compliance Reports

**OWASP Agentic AI Top 10** (ASI07–ASI10):
- Maps configured SLOs to OWASP control categories
- Produces `mitigated` / `partially_mitigated` / `not_mitigated` status for each

**EU AI Act Evidence**:
- Generates compliance evidence scaffold (governance, risk management, transparency logs)

### API Endpoints (15)

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/tenants` | Create tenant |
| `GET` | `/api/v1/tenants/me` | Get current tenant |
| `POST` | `/api/v1/agents` | Register agent |
| `GET` | `/api/v1/agents` | List agents |
| `POST` | `/api/v1/slis` | Create SLI definition |
| `GET` | `/api/v1/slis` | List SLIs |
| `POST` | `/api/v1/slos` | Create SLO |
| `GET` | `/api/v1/slos` | List SLOs |
| `GET` | `/api/v1/status` | **Core** — SLO dashboard |
| `GET` | `/api/v1/alerts` | List alerts |
| `POST` | `/api/v1/alerts/{id}/resolve` | Resolve alert |
| `GET` | `/api/v1/compliance/owasp` | OWASP report |
| `GET` | `/api/v1/compliance/eu-ai-act` | EU AI Act evidence |
| `POST` | `/v1/traces` | **Core** — ingest OTel spans |

### CLI (`sloctl`)

```
sloctl apply <file>    Apply SLO/RiskBudget YAML definitions
sloctl status          Print current SLO status dashboard
sloctl report <std>    Generate compliance report (owasp, eu-ai-act)
```

### Data Models (7 tables)

- **Tenant** — organization with slug and API key
- **Agent** — registered agent with environment, framework, model_provider
- **SLI** — service level indicator definition
- **SLO** — service level objective with target, comparator, window
- **Metric** — time-series data point derived from spans
- **ErrorBudget** — budget tracking per SLO period
- **Alert** — burn-rate alert with severity
- **OtelSpan** — raw ingested span data

---

## 4. How the Three Services Connect

```
                     ┌─────────────────────┐
                     │  SLO Platform       │
                     │  (port 8000)        │
                     │                     │
                     │  Ingests OTel spans │
                     │  Evaluates SLOs     │
                     │  Error budgets      │
                     │  Compliance reports │
                     └────────┬────────────┘
                              │ reads metrics
                              │ from tool calls
                              │
     ┌────────────────────────┴────────────────────────┐
     │                                                 │
     ▼                                                 ▼
┌────────────────────┐                  ┌─────────────────────┐
│ Circuit Breaker    │                  │ Chaos Toolkit       │
│ (port 8001)        │                  │ (port 8002)         │
│                    │                  │                     │
│ Real-time safety   │                  │ Pre-production      │
│ Intercept tool     │                  │ Fault injection     │
│   calls            │                  │ Resilience scoring  │
│ Risk + anomaly     │                  │ 15 built-in         │
│ Policies + kill    │                  │   scenarios         │
│ Rollback engine    │                  │ CI/CD integration   │
└────────────────────┘                  └─────────────────────┘
```

### Lifecycle

```
DEVELOPMENT → Chaos Toolkit validates agent resilience
                   │
                   ▼
STAGING → Circuit Breaker enforces policies on real tool calls
                   │
                   ▼
PRODUCTION → SLO Platform monitors SLIs, alerts on breaches
                                             │
                                             ▼
                              Compliance reports (OWASP, EU AI Act)
```

### Shared Concepts Across All Three

- **Tenant isolation** via header-based auth (X-Tenant-ID or X-API-Key)
- **Agent identity** tracked consistently across all three
- **YAML-driven configuration** for policies, scenarios, and SLOs
- **Tool-level granularity** — all three operate at the individual tool-call level
- **Provider-agnostic** — no dependency on any specific LLM provider (OpenAI, Anthropic, open-source, or no-LLM all work)

---

## 5. Architecture & Technology

### Common Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (async) |
| Database | SQLAlchemy 2.0 ORM with async sessions |
| DB Driver | asyncpg (PostgreSQL) / aiosqlite (SQLite) |
| Config | pydantic-settings |
| Serialization | Pydantic v2 |
| CLI | Typer + httpx |
| YAML | PyYAML + Pydantic models |
| Testing | pytest + pytest-asyncio + httpx ASGITransport |
| Coverage | pytest-cov with thresholds (75%/70%/80%) |

### Per-Service Dependencies

| Circuit Breaker | Chaos Toolkit | SLO Platform |
|----------------|---------------|--------------|
| numpy (Z-scores) | — | apscheduler (future scheduling) |

### Testing Approach

All three use the same pattern: **in-memory SQLite** with `create_all` on startup, httpx `ASGITransport` for API tests, and dependency overrides to inject the test database session. No Docker, no test containers, no external services required for test execution.

### Total Codebase

| Metric | Circuit Breaker | Chaos Toolkit | SLO Platform | Total |
|--------|----------------|---------------|--------------|-------|
| Source lines | 969 | 700 | ~1200 | ~2,869 |
| Test functions | 40 | 48 | ~32 | 120 |
| API endpoints | 14 | 14 | 15 | 43 |
| DB tables | 6 | 4 | 8 | 18 |
| Source files | 16 | 17 | 14 | 47 |

---

## 6. Running the Platform

### Prerequisites

- Python 3.11+
- PostgreSQL (for Circuit Breaker and SLO Platform)
- SQLite (built-in, for Chaos Toolkit)

### Installation

```bash
# Each service is a separate installable package
cd agent-circuit-breaker && pip install -e ".[dev,test]"
cd agent-chaos-toolkit && pip install -e ".[dev,test]"
cd agent-slo-platform && pip install -e ".[dev,test]"
```

### Running

```bash
# Each service starts independently
cd agent-circuit-breaker && uvicorn circuit_breaker.api:app --port 8001
cd agent-chaos-toolkit && uvicorn chaos_toolkit.api:app --port 8002
cd agent-slo-platform && uvicorn agent_slo.api:app --port 8000
```

### Configuration

Each service uses environment variables prefixed as `Settings` fields:

```bash
# Circuit Breaker
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/circuit_breaker
API_KEY=dev-api-key
LOG_LEVEL=info
KILL_SWITCH_TTL_SECONDS=3600

# Chaos Toolkit
DATABASE_URL=sqlite+aiosqlite:///chaos_toolkit.db
API_KEY=dev-api-key
LOG_LEVEL=info

# SLO Platform
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agent_slo
API_KEY=dev-api-key
LOG_LEVEL=info
```

### Testing

```bash
# Run all tests for any service
pytest tests/ -v --tb=short
```
