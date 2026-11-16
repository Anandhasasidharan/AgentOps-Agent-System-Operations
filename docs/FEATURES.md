# AgentOps: Feature Map

## Regression fixes — 2026-11-16

- Dashboard, Gateway, and LangChain now declare `pytest-cov` in their dev extras,
  so isolated CI installs support the coverage flags used by the test matrix.


- HTTP intercept and chaos requests forward the full authenticated API key to
  OTLP ingestion. Export failures emit credential-free structured warnings;
  event-driven chaos runs with no raw credential skip telemetry visibly.
- SLO creation accepts an optional agent UUID and validates agent and SLI
  ownership. An agent-scoped SLI supplies the default scope; conflicting scope
  is rejected. Filtered status includes the agent ID internally.
- SDK `create_slo` accepts `agent_id`; callers use the SLO API agent UUID in
  intercept requests so breach policies match the same identity.
- Dashboard event fields render with text nodes instead of HTML concatenation.
  Its regression executes delivered JavaScript with malicious event values and
  rejects unsafe HTML assignments (requires Node.js; installed in dashboard CI).
- `make closed-loop-demo` runs five real HTTP services, disposable SQLite, and
  a local NATS broker. It checks authenticated automatic telemetry, public API
  SLO scope, scheduled breach publication without status polling, and lockdown
  limited to the intended agent. CI runs it with the durable recovery check.

## Implementation update — 2026-11-16

The older audit rows below are historical and have not all been revalidated.
Current changes:

- Gateway HTTP and WebSocket authentication is mandatory, resolves tenant IDs,
  and filters buffered and live events. Header/query contract and isolation
  regression tests are in `agent-gateway/tests/test_api.py`.
- Dashboard requires a configured tenant API key through HTTP Basic auth or
  `X-API-Key`; health and metrics remain public. Regression tests cover denial
  and authorized access.
- Execution graphs are separate per tenant, including graph API output.
- SLO evaluation runs periodically without a dashboard request (default 30s),
  with per-tenant failure isolation and shutdown cancellation.
- Production Compose has explicit Uvicorn commands and consistent service ports;
  database password and public WebSocket URL are required.
- `make guarded-demo` verifies allow, block, and fail-closed outage behavior over
  actual localhost HTTP using disposable SQLite and no model credentials.

- SLO breach events now wait for JetStream storage acknowledgements, use stable
  message IDs across publish retries, and resume a durable queue after restarts.
  Enforcement receipts commit with policies. Invalid events terminate delivery;
  transient enforcement errors request redelivery. `examples/durable_breach.py`
  verifies offline delivery, transient failure retry, and a real broker restart.
- CI gates image builds on the durable recovery check and clean installation.

Still outstanding: a transactional producer outbox, distributed evaluator
coordination, comprehensive schema migrations, an MCP proxy, published detector
benchmarks, native-engine parity, and a verified public deployment. These changes
do not establish those capabilities.


The "what is actually true" document. It is deliberately unflattering.

**Sources and confidence**
- Rows come from a code audit at `c55af60` (branch `feature/c-policy-engine`).
- Rows marked **†** were independently re-checked against `main` at `bff4c4c` on 2026-10-23.
- Rows without † come from the audit only and have not been independently verified. The branch was not on GitHub when I checked, so anything about the native engine is audit-only.
- Update the status rows in the same PR that changes the feature.

**Legend**

| Mark | Meaning |
|---|---|
| ✅ | Shipped, tested, works as documented |
| 🟡 | Shipped, works, but has a material limitation |
| 🔴 | Shipped but broken, unreachable, or contradicts its documentation |
| ⚪ | Not built |

Companion documents: [`ROADMAP.md`](ROADMAP.md) (what and why), [`PLAN.md`](PLAN.md) (how, estimates, acceptance evidence).

---

## 1. Enforcement: Circuit Breaker (`:8001`)

The core product. `POST /v1/intercept` decides allow, block, kill, or alert before a tool executes.

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Intercept orchestration | ✅ | `proxy.py`, staged pipeline, single entry point | n/a |
| Kill switch | ✅ | `kill_switch.py`: TTL, activate and release, forces `AgentState.is_killed` | n/a |
| Risk scoring | ✅ | `risk_engine.py`: 4 weighted factors, tool weights, input patterns | n/a |
| Anomaly detection | ✅ | `anomaly_engine.py`: multiple detectors, weighted composite | n/a |
| DTMC prediction | 🟡 | `dtmc.py`, `predictor.py`: PAC bound, `__BLOCKED__` and `__ERROR__` sinks. Wording of the "guarantee" is unreviewed | M4 |
| Graph monitor | ✅ | `graph_monitor.py`: z-score over agent-to-tool edges, needs at least 3 samples | n/a |
| Policy engine, 8 types | ✅ | `policy_engine.py`: all 8 match. Conditions are now typed and validated (M1.1); cross-midnight windows are rejected by schema | n/a |
| Policy priority ordering | ✅ | `load_policies` orders by `priority.desc()`, first match wins | n/a |
| Incident creation | ✅ | `incident_engine.py`: severity, category, action record per block | n/a |
| Rollback and compensation | 🟡 | `rollback_engine.py`: inverse tools exist, but compensation is recorded, never executed | v1.1 |
| Agent state tracking | 🟡 | `state_tracker.py`: 5-minute windows; reads `call_count` before the column default applies on new rows | M1 |
| **Condition schema validation** | ✅ | `policy_conditions.py`: one typed model per policy type, shared by API and `cbctl apply`; unknown keys rejected with 422. `tests/integration/test_policy_schema.py` covers one misspelled key per type | n/a |
| **Auto-lockdown on SLO breach** | ✅ | Breach event carries `agent_id`; `handle_slo_breach` creates an agent-scoped priority-100 block policy; `tests/integration/test_closed_loop.py` proves the next intercept is blocked | n/a |
| Native C engine | 🔴 | `agentops-engine/` reported uncommitted, untested, Linux-only `.so`, not in CI (audit only) | M5 |
| Embedded in-process mode | ⚪ | The real benefit of a native engine (see section 9) | M5.5 |
| Per-tenant policy isolation | 🟡 | Filtered by `tenant_id`; all tenants share one physical database | v1.1 |
| Intercept idempotency | ⚪ | No `Idempotency-Key`; a retried call double-counts and double-blocks | M3.2 |
| Intercept timeout policy | ⚪ | No defined behavior when the breaker is slow | M3.1 |

### Condition keys are now validated

Before M1, `PolicyCreate.conditions` accepted any JSON object. `_matches_policy`
then read keys such as `max_calls`. A typo produced a policy that loaded,
reported as enabled, showed in `GET /api/v1/policies`, and silently never fired.

`policy_conditions.py` now defines one typed model per policy type and is used
by both the HTTP API and `cbctl apply`. Unknown keys are rejected with 422, so
the worst failure mode (looks deployed, is not) is closed. The tests in
`tests/integration/test_policy_schema.py` cover one misspelled key per type.

---

## 2. Resilience Testing: Chaos Toolkit (`:8002`)

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Built-in scenarios | ✅ | `scenarios.py`: targets across llm, tool, rag, mcp | n/a |
| YAML scenario definitions | ✅ | `parse_scenario_yaml`, `chaosctl apply` | n/a |
| Fault injection | ✅ | `injector.py`, per-target modules | n/a |
| Resilience scoring | ✅ | `scoring.py`: 1.0, 0.7, 0.2, 0.0 bands, pass at 0.7 or above | n/a |
| Recommendations | ✅ | `scoring.py`: critical, warning, info thresholds | n/a |
| JUnit XML and GitHub summary | ✅ | `reporters/ci.py` | n/a |
| LLM scenario proposer | 🟡 | Needs `OPENAI_API_KEY`; returns `[]` on any exception | v1.1 |
| Closed-loop refine | 🟡 | Same; failures are invisible | v1.1 |
| **Sync fault injection** | 🔴† | Target modules `await asyncio.sleep(...)` inside a synchronous request (tool timeout draws 25-120s†); `seed.py` needs a workaround and skip-list | M6.5 |
| Experiment isolation | ⚪ | Experiments run in-process; a slow injection ties up a worker | M6.5 |
| Auto-run on incident | 🔴 | Subscribes to `agentops.cb.incident.*`, runs up to 3 experiments inline; malformed payloads are swallowed by a broad try/except | v1.1 |
| Chaos against the real agent | ⚪ | Scenarios inject simulated faults; no adapter perturbs a customer's live agent | v1.1 |

---

## 3. Observability: SLO Platform (`:8000`)

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| OTLP trace ingestion | ✅ | `receiver.py`: `POST /v1/traces`, GenAI semantic conventions | n/a |
| SLI extraction | ✅ | `extractor.py`: weighted rates, p99 latency | n/a |
| SLO evaluation | ✅ | `engine.py`: `gt`, `lt`, `eq` comparators, window bounds | n/a |
| Burn-rate math | ✅ | `engine.py`: multi-window thresholds | n/a |
| Error budgets | ✅ | `error_budgets` table and remaining-fraction math | n/a |
| Alerts and dedupe | ✅ | `alerts.py`: dedupes on `(severity, threshold)` of unresolved | n/a |
| OWASP Agentic controls | 🟡 | `compliance.py`: statically asserted, not measured | v1.1 |
| EU AI Act report | 🟡 | Scaffolding; article mapping is asserted, not evidenced | v1.1 |
| Risk budgets | 🔴 | `risk_budget.py` complete and tested in isolation, but no API route and no caller; reachable only via `sloctl apply` | v1.1 |
| SLO YAML apply | 🟡 | `sloctl apply` works; no server-side apply endpoint | v1.1 |
| Multi-environment modelling | ✅ | Agents keyed on `(tenant, environment, name)` | n/a |
| Trust score | 🟡 | Derived in `receiver.py`; advertised as a headline feature with no endpoint, formula docs, or dedicated tests | v1.1 |
| Alert delivery (webhook, Slack, PagerDuty) | ⚪ | Alerts are stored, not delivered | v1.1 |

---

## 4. Surfaces

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Gateway NATS-to-WebSocket | ✅ | `agent-gateway:8004`: ring buffer, `/ws`, replay via `?since=` | n/a |
| **Gateway auth** | 🔴† | Optional: `if api_key and not validate(...)`. Omit the key and you are in | M2.3 |
| Dashboard health page | 🟡 | Server-rendered HTML string, 3 s polling, 3 upstreams (not the gateway) | M2 |
| **Dashboard auth** | 🔴 | None; any visitor sees live incident data | M2.3 |
| Dashboard as a product surface | ⚪ | No policy editor, incident timeline, agent explorer, or SLO drill-down | v1.1 |
| CLI `cbctl` | 🟡 | `apply` only; no `status`, `tail`, `kill` | v1.1 |
| CLI `chaosctl` | ✅ | apply, run, batch, report, seed | n/a |
| CLI `sloctl` | ✅ | apply | n/a |

---

## 5. Adapters and SDK

This layer decides whether anyone can adopt the platform.

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Python SDK | 🟡 | `agentops-sdk`: thin `httpx` wrapper. Fail mode is implemented and tested; retry, pooling, and configurable intercept timeout remain M3.5 | M3.5 |
| **SDK fail mode** | ✅ | `agentops-sdk` denies on unreachable, non-2xx, and malformed verdicts by default; `AGENTOPS_FAIL_MODE=open` is explicit. `tests/test_fail_mode.py` | n/a |
| LangChain adapter | 🟡 | `wrap_tool` and callback handler | M3.5 |
| **LangChain fail mode** | ✅ | Defaults to closed on unreachable, non-2xx, and malformed verdicts in both the wrapper and callback. `AGENTOPS_FAIL_MODE=open` is tested. Structured degraded-decision log | n/a |
| Direct HTTP contract | ✅ | Any language can `POST /v1/intercept` | n/a |
| MCP proxy | ⚪ | Highest-value gap; `proxy.py` is the intercept pipeline, not an MCP proxy (confirm in M3.3) | M3.3 |
| OpenAI Agents SDK adapter | ⚪ | | M3.4 |
| Anthropic tool-use adapter | ⚪ | | v1.1 |
| LangGraph, CrewAI, AutoGen | ⚪ | | v1.1 |
| TypeScript SDK | ⚪ | | v1.1 |
| `@guarded` decorator | ⚪ | Framework-agnostic | v1.1 |
| Drop-in proxy mode | ⚪ | No "point your base URL here" mode | v1.1 |
| Packages on PyPI | ⚪ | | R1 |

---

## 6. Data and Multi-Tenancy

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Tenant model and API keys | ✅ | `agentops_core`: `slug:token`, hashed, shown once | n/a |
| Key rotation | ✅ | `POST /api/v1/keys/rotate` | n/a |
| Rate limiting | 🟡 | Sliding 60 s window, `/health` and `/metrics` bypass, in memory so single replica only. `RATE_LIMIT_RPM=0` fixed with a regression test (`7c17c19`) | v1.1 |
| **Database migrations** | 🔴† | All three DB services call `Base.metadata.create_all` at startup†. Only the SLO Platform has Alembic (one migration, per the audit), so even there `create_all` undermines it | M6.2 |
| Shared database | 🟡 | All services share one database; table names happen to be disjoint, but three ORMs share one schema | v1.1 |
| Audit log | ⚪ | No record of who changed which policy | M6.4 |
| Data retention and deletion | ⚪ | No TTL, purge, or erasure path | v1.1 |
| PII redaction in traces | ⚪ | Raw `tool_input` is stored verbatim | M6.1 |

---

## 7. Operations and Release

| Feature | Status | Evidence and notes | Milestone |
|---|---|---|---|
| Docker Compose stack | ✅ | Healthchecks on Postgres only | n/a |
| Single Dockerfile, `ARG SERVICE` | ✅ | Clean multi-service build | n/a |
| Prometheus metrics | ✅ | All services expose `/metrics`, distinct prefixes | n/a |
| **Fresh-install reliability** | ✅ | Dependencies pin `sqlalchemy[asyncio]>=2.0,<2.2`; a clean-venv CI job installs all packages and runs every suite | n/a |
| Pinned lint and format tools | ✅ | `ruff==0.16.10` and `black==26.10.0` pinned in dev extras and the lint job; `make lint` and `make format-check` pass | n/a |
| **CI coverage** | ✅ | Matrix covers all 9 Python packages plus `agentops-engine`; dashboard, gateway, LangChain, and engine tests now gate merges | n/a |
| Clean-install CI job | ✅ | `clean-install` job creates a new venv, installs every package in order, and runs all suites | n/a |
| mypy | 🔴 | `strict = true` configured and never run | M6.6 |
| Python 3.12 and 3.13 in CI | ⚪ | CI pins 3.11; classifiers claim 3.12 | M6.6 |
| Grafana | 🔴† | Anonymous Admin, password `admin`. Fine locally, never public | M2.3 |
| Railway config | 🟡 | Unverified; no deploy has been run. Delete or verify | M2.3 |
| Terraform, Helm | 🟡 | Folders present, removed from CI in `437c50c`, unmanaged. Decision deferred to M2.3; see `FOLLOWUPS.md` | M2.3 |
| Graceful shutdown | 🟡† | Gateway still on deprecated `@app.on_event` | M6.3 |
| Health checks | 🟡† | `/health` returns `{"status":"ok"}` unconditionally; no DB or NATS probe | M6.3 |
| NATS delivery guarantees | 🔴 | Fire-and-forget publish. Whether incidents are also persisted independent of publishing is unchecked; if yes, events are notifications only | M3.6 |
| Structured logging and tracing | 🟡 | `logger.info` plus OTLP export; no correlation IDs | M6.3 |
| Public live demo | ⚪ | | M2.3 |
| Runnable end-to-end example | ⚪ | No `examples/` quickstart | M2.1 |
| Release process (tags, changelog, PyPI) | ⚪ | | R1 |
| Load and soak testing | ⚪ | One bench harness for the policy engine only | v1.1 |

---

## 8. Governance

| Feature | Status | Milestone |
|---|---|---|
| Audit trail of policy, kill, and incident changes | ⚪ | M6.4 |
| Policy dry-run and simulation | ⚪ (stretch) | M6 stretch |
| RBAC (roles, scopes) | ⚪ | v1.1 |
| SSO and OIDC | ⚪ | v1.1 |
| Approval workflows (`reroute` exists but routes nowhere) | ⚪ | v1.1 |
| Policy versioning, diff, and rollback | ⚪ | v1.1 |

---

## 9. What is genuinely differentiated

These are real or nearly real. Each carries the condition that makes it honest.

1. **Fast policy evaluation with formal bounds.** The Python baseline already shows engine-only throughput around 35k calls/s against about 731 calls/s end to end (audit figures, unverified), so evaluation is on the order of tens of microseconds and about 2% of a request. A native engine therefore does not speed up the server path much; its value is **embedded in-process mode**, where there is no network hop. The DTMC and PAC bound is a real asset once its wording is checked (M4.3).
2. **Closed-loop SLO to enforcement.** An SLO breach tightens policy automatically. The design is distinctive, but it is broken today (section 1), so the claim is unearned until M1.2 passes. Whether any competitor does this is not established; do not claim it until it is.
3. **Chaos testing scoped to agents.** Failure modes across llm, tool, rag, and mcp, aimed at agent behavior rather than infrastructure. The claim that competitors only inject at the infrastructure layer is unverified.
4. **One decision record per tool call.** Risk, anomaly, policy, incident, and span joined on a `tool_call_id`. That is an audit trail once it is made trustworthy (M6.4).
5. **A framework-agnostic intercept contract.** One HTTP endpoint, any language. Adapters stay thin because they can.

Detection quality of the layered detectors is **unmeasured**. M4 compares each layer against a plain allowlist baseline before any of them is called an advantage.

---

## 10. Anti-features: deliberately do not build

- An LLM gateway or inference proxy. Crowded and commoditised.
- Eval and dataset tooling. Owned by LangSmith, Braintrust, Promptfoo.
- A general APM backend. Export to Grafana and Datadog instead.
- A hosted multi-tenant SaaS. Requires billing, SOC 2, and on-call.
- A custom agent framework. It would invert the integration story.
- Mechanistic interpretability. Trust scores are operational metrics, not interpretability.

---

## 11. Contracts to stabilize

| Contract | Where | Action |
|---|---|---|
| HTTP API | `/v1/*` | OpenAPI export, changelog, deprecation policy |
| Policy file and `conditions` | YAML and JSON | One typed schema and condition validation shipped in M1.1; `version:` field and JSON Schema export remain |
| Events | NATS topics | Schema per topic, versioned |
| Telemetry | OTel attributes | Document names and units |
| Native ABI | `agentops.h` | `AO_ABI_VERSION`, stable struct layouts |
