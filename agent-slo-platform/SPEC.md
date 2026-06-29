# Agent SLO Platform — Production v1 Specification

> Companion to `../domain-1-agentops.md` and `../agentops-unique-features.md`.
> Project: AgentOps — Agent SLO Platform.
> Target: Production v1 with tests + docs.

---

## 1. Overview

The Agent SLO Platform defines, measures, and alerts on Service Level Objectives for AI agents. Unlike generic infrastructure APM, it uses **agent-native signals**: task success rate, hallucination rate, tool accuracy, cost-per-task, steps-to-completion, and human escalation rate.

### What v1 ships

- YAML-based SLO definition language.
- OpenTelemetry-native ingestion (OTLP/HTTP).
- Burn-rate and error-budget engine with multi-threshold alerting.
- Multi-tenant dashboards API.
- Two unique differentiators from `agentops-unique-features.md`:
  1. **Risk-Budget SLOs** — carbon-budget-style risk consumption per agent/session.
  2. **OWASP Agentic ASI01–ASI10 Evidence Generator** — auditor-ready compliance artifacts.

### What v1 explicitly does NOT ship

- Web UI dashboard frontend (REST API only; CLI + optional minimal HTML status page).
- Advanced ML anomaly detection (v2).
- Built-in SSO (v2; rely on API key / tenant header for v1).

---

## 2. Goals & Non-Goals

### Goals

1. Define SLOs in YAML with rolling windows and burn-rate alerts.
2. Ingest OpenTelemetry traces from Langfuse, Phoenix, OpenLLMetry, or direct SDKs.
3. Compute SLIs from agent-native span attributes.
4. Track error budgets and alert at 2%, 5%, and 10% burn thresholds.
5. Provide per-tenant, per-agent, per-environment status APIs.
6. Include risk-budget SLOs as a first-class primitive.
7. Generate OWASP Agentic evidence reports for audits.
8. Ship with Docker Compose, Alembic migrations, pytest suite (≥80% coverage), and docs.

### Non-Goals

- Replacing Langfuse/Phoenix as the primary observability store.
- Supporting non-OTel ingestion paths.
- Multi-region HA in v1 (single-node Postgres; HA guide is v2).

---

## 3. Architecture

```
┌─────────────┐      OTLP/HTTP       ┌──────────────────────┐
│ Agent / SDK │─────────────────────▶│  Agent SLO Platform  │
│  (OTel)     │                      │  FastAPI + SQLAlchemy│
└─────────────┘                      │  + Celery (optional) │
                                     └──────────┬───────────┘
                                                │
                       ┌────────────────────────┼────────────────────────┐
                       ▼                        ▼                        ▼
                ┌─────────────┐        ┌──────────────┐        ┌──────────────┐
                │   PostgreSQL│        │   SLI/Budget │        │   Alerting   │
                │   (metrics  │        │   Engine     │        │   (webhooks) │
                │   + SLOs)   │        │              │        │              │
                └─────────────┘        └──────────────┘        └──────────────┘
```

### Components

1. **OTel Receiver** (`agent_slo.receiver`): accepts OTLP/HTTP trace requests, normalizes spans, persists raw spans and derived metrics.
2. **SLI Extractor** (`agent_slo.extractor`): maps OTel GenAI semantic conventions + custom attributes to agent-native SLIs.
3. **SLO Engine** (`agent_slo.engine`): evaluates SLOs against SLIs in rolling windows, tracks error budgets, computes burn rates.
4. **Alert Engine** (`agent_slo.alerts`): evaluates burn-rate thresholds and dispatches webhooks.
5. **Dashboards API** (`agent_slo.api`): FastAPI routes for SLOs, SLIs, budgets, alerts, status.
6. **Compliance Module** (`agent_slo.compliance`): OWASP Agentic evidence generator.
7. **CLI** (`agent_slo.cli`): `sloctl apply -f slo.yaml`, `sloctl status`, `sloctl report`.

---

## 4. Data Model

### Core Entities

```python
class Tenant(Base):
    id: UUID
    slug: str  # unique
    name: str
    created_at: datetime

class Agent(Base):
    id: UUID
    tenant_id: UUID
    environment: str  # prod, staging, dev
    name: str
    framework: str | None  # openai-agents, langchain, crewai, etc.
    model_provider: str | None

class ServiceLevelIndicator(Base):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None  # None = global
    name: str  # task_success_rate, hallucination_rate, cost_per_task, etc.
    metric_type: str  # ratio | threshold | budget | count
    source: str  # otel_attribute | computed
    config: dict  # e.g., {"numerator_attr": "gen_ai.eval.success", "denominator_attr": "gen_ai.request.count"}

class ServiceLevelObjective(Base):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None
    name: str
    description: str
    sli_id: UUID
    target: float  # e.g., 0.95 for 95%
    comparator: str  # gt | lt | eq
    window: str  # 7d, 1h, 30m
    burn_rate_alert_thresholds: list[float]  # [0.02, 0.05, 0.10]
    risk_budget: dict | None  # for Risk-Budget SLOs
    labels: dict

class Metric(Base):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None
    sli_id: UUID
    timestamp: datetime
    value: float
    count: int  # sample count backing the value
    window_start: datetime
    window_end: datetime

class ErrorBudget(Base):
    id: UUID
    slo_id: UUID
    period_start: datetime
    period_end: datetime
    total_budget: float  # e.g., 1 - target
    consumed: float
    remaining: float

class Alert(Base):
    id: UUID
    tenant_id: UUID
    slo_id: UUID
    severity: str  # info | warning | critical
    threshold: float
    burn_rate: float
    fired_at: datetime
    resolved_at: datetime | None

class OtelSpan(Base):
    # raw OTLP span persisted for replay / evidence
    trace_id: bytes
    span_id: bytes
    parent_span_id: bytes | None
    tenant_id: UUID
    agent_id: UUID | None
    name: str
    kind: int
    start_time: datetime
    end_time: datetime
    attributes: dict
    events: list[dict]
    status: dict
```

---

## 5. SLO YAML Specification

```yaml
apiVersion: agentops.io/v1
kind: SLO
metadata:
  name: task-success-rate
  tenant: acme-corp
  environment: production
  agent: onboarding-agent
spec:
  sli: task_success_rate
  target: 0.95
  comparator: gt
  window: 7d
  burnRateAlerts:
    - threshold: 0.02
      severity: info
    - threshold: 0.05
      severity: warning
    - threshold: 0.10
      severity: critical
  labels:
    team: agent-platform
    priority: p1

---
apiVersion: agentops.io/v1
kind: RiskBudget
metadata:
  name: destructive-action-risk
  tenant: acme-corp
  environment: production
spec:
  budget: 5
  window: 1h
  weights:
    delete_file: 2
    send_email: 1
    update_record: 0.5
  action: require_approval
  burnRateAlerts:
    - threshold: 0.50
      severity: warning
    - threshold: 0.90
      severity: critical
```

### Supported SLIs

| SLI name | Type | OTel attributes |
|---|---|---|
| `task_success_rate` | ratio | `gen_ai.eval.success` / `gen_ai.eval.total` |
| `hallucination_rate` | ratio | `gen_ai.eval.hallucination` / `gen_ai.eval.total` |
| `tool_accuracy` | ratio | `gen_ai.tool.success` / `gen_ai.tool.calls` |
| `cost_per_task` | threshold | `gen_ai.usage.cost` per `gen_ai.session.id` |
| `steps_to_completion` | threshold | count of spans per session |
| `human_escalation_rate` | ratio | `agentops.escalation` / `gen_ai.eval.total` |
| `latency_p99` | threshold | `gen_ai.response.duration` p99 over window |
| `token_usage` | threshold | `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` |

---

## 6. OpenTelemetry Ingestion

### Receiver

- `POST /v1/traces` — OTLP/HTTP JSON/Protobuf.
- Authentication: `X-API-Key` header mapped to tenant.
- Agent resolution: `agentops.agent.id` or `service.name` span attribute.

### Required Span Attributes

| Attribute | Meaning |
|---|---|
| `gen_ai.system` | Model provider (openai, anthropic, etc.) |
| `gen_ai.request.model` | Model name |
| `gen_ai.usage.input_tokens` | Input tokens |
| `gen_ai.usage.output_tokens` | Output tokens |
| `gen_ai.eval.success` | 1 if task succeeded |
| `gen_ai.eval.hallucination` | 1 if hallucination detected |
| `gen_ai.tool.name` | Tool name |
| `gen_ai.tool.success` | 1 if tool call succeeded |
| `agentops.agent.id` | Agent identifier |
| `agentops.environment` | prod / staging / dev |
| `agentops.risk_weight` | For risk-budget SLOs (optional) |

### Design Notes

- Persist raw spans in `otel_spans`.
- Derive metrics asynchronously via materialized view or background job (Celery beat / APScheduler).
- For v1, use synchronous materialization on ingestion to keep the stack simple.

---

## 7. Error Budget & Burn Rate Math

### Error Budget

```
budget = 1 - target           # e.g., target 0.95 => budget 0.05
consumed = bad_events / total
total_budget_over_window = budget * total
remaining = 1 - consumed
```

### Burn Rate

```
burn_rate = consumed_budget / elapsed_fraction_of_window
```

Example: in a 7-day window, after 12 hours, 2% of budget consumed:
- elapsed_fraction = 12 / 168 = 0.0714
- burn_rate = 0.02 / 0.0714 = 0.28

Alert thresholds: `0.02`, `0.05`, `0.10` (doc's recommendation) translate to:
- 2% burn in first 2% of window → will exhaust budget exactly on time
- 10% burn in first 2% of window → will exhaust budget 5× faster

### Risk-Budget Burn

```
weighted_risk_consumed = sum(tool_calls * risk_weight)
risk_budget_consumed = weighted_risk_consumed / risk_budget_total
```

---

## 8. Unique Feature: Risk-Budget SLOs

A first-class primitive that budgets **risk**, not just errors.

### Use Case

An agent is allowed to call destructive tools, but only up to a weighted risk budget per hour. Exceeding the budget triggers `require_approval` or `kill`.

### Implementation

- `RiskBudget` kind in YAML.
- Store `risk_budget` column on `ServiceLevelObjective`.
- When ingesting spans, if `agentops.risk_weight` or a tool-name→weight mapping exists, accumulate into the risk budget.
- Alert on `risk_budget_consumed`.

### Differentiation

No competitor has risk-budget SLOs. `circuitbreaker.dev` has token/cost budgets. Microsoft AGT has cost SLOs. Risk-weighted action budgets are new.

---

## 9. Unique Feature: OWASP Agentic Evidence Generator

Generates an audit artifact mapping the platform's controls to OWASP Agentic AI risks.

### Output

```json
{
  "generated_at": "2026-06-25T00:00:00Z",
  "standard": "OWASP Agentic AI Top 10 2026",
  "tenant": "acme-corp",
  "controls": [
    {
      "risk_id": "ASI07",
      "risk_name": "Uncontrolled Costs",
      "status": "mitigated",
      "evidence": [
        "SLO 'cost-per-task' target < $0.50 over 7d",
        "RiskBudget 'cost-explosion' with kill action at 90%"
      ]
    },
    {
      "risk_id": "ASI08",
      "risk_name": "Cascading Agent Failures",
      "status": "partially_mitigated",
      "evidence": [
        "Latency SLO p99 < 10s across agent fleet"
      ],
      "gaps": [
        "No cross-agent blast-radius kill decision in v1"
      ]
    }
  ]
}
```

### Implementation

- YAML mapping file: `owasp_agentic_controls.yaml` linking each risk to required SLO kinds.
- `sloctl report owasp --tenant acme-corp` command.
- API endpoint: `GET /api/v1/compliance/owasp`.

---

## 10. API Surface

### SLOs

- `GET /api/v1/slos`
- `GET /api/v1/slos/{id}`
- `POST /api/v1/slos` (YAML or JSON body)
- `PATCH /api/v1/slos/{id}`
- `DELETE /api/v1/slos/{id}`

### SLIs

- `GET /api/v1/slis`
- `GET /api/v1/slis/{id}`

### Metrics / Status

- `GET /api/v1/status?tenant=&agent=&environment=`
- `GET /api/v1/metrics?sli=&window=`
- `GET /api/v1/budgets/{slo_id}`

### Ingestion

- `POST /v1/traces` — OTLP/HTTP

### Compliance

- `GET /api/v1/compliance/owasp`
- `GET /api/v1/compliance/eu-ai-act`

### Alerts

- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{id}/resolve`

---

## 11. Testing Strategy

### Unit Tests

- Pydantic YAML parsing
- SLI math
- Burn-rate calculations
- Risk-budget accumulation

### Integration Tests

- OTel trace ingestion round-trip
- SLO evaluation against stored metrics
- Alert firing and webhook delivery
- Compliance report generation

### Fixtures

- Mock OTLP trace payloads for Langfuse / Phoenix / OpenLLMetry.
- Pre-computed metric windows.

### Coverage Target

≥80% unit test coverage; integration tests for every API route.

---

## 12. Project Structure

```
agent-slo-platform/
├── README.md
├── SPEC.md
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── agent_slo/
│       ├── __init__.py
│       ├── api.py              # FastAPI app
│       ├── cli.py              # sloctl
│       ├── config.py           # Pydantic settings
│       ├── db.py               # SQLAlchemy session + engine
│       ├── models.py           # SQLAlchemy tables
│       ├── schemas.py          # Pydantic request/response models
│       ├── receiver.py         # OTLP/HTTP handler
│       ├── extractor.py        # SLI extraction from spans
│       ├── engine.py           # SLO + budget evaluation
│       ├── alerts.py           # Alert engine + webhooks
│       ├── compliance.py       # OWASP + EU AI Act reports
│       └── risk_budget.py      # Risk-budget math
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── docs/
    ├── deployment.md
    ├── api.md
    └── architecture.md
```

---

## 13. Deployment

### Local Dev

```bash
docker compose up -d db
cd agent-slo-platform
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
pytest
uvicorn agent_slo.api:app --reload
```

### Production v1

- Single container + managed Postgres.
- Run `sloctl apply -f slos/` in CI/CD.
- Webhooks to PagerDuty/Slack via alert receiver config.

---

## 14. Roadmap after v1

- v1.1: Alertmanager + PagerDuty native integrations, Grafana dashboard JSON.
- v1.2: Anomaly detection on SLI time series.
- v2.0: Multi-region HA, ClickHouse for span storage, SSO/RBAC.

