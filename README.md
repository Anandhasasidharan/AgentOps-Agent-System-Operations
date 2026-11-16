<div align="center">

# 🤖 AgentOps — AI Agent Safety & Observability Platform

**Runtime safety · Resilience testing · SLO compliance · Predictive analytics**

[![CI/CD](https://img.shields.io/github/actions/workflow/status/Anandhasasidharan/AgentOps-Agent-System-Operations/agentops.yml?branch=main&logo=github&label=CI%2FCD)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker)](https://hub.docker.com/u/asd492)
[![License](https://img.shields.io/badge/license-MIT-22BA5A)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Anandhasasidharan/AgentOps-Agent-System-Operations?logo=git)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/commits/main)
[![Docker Pulls](https://img.shields.io/docker/pulls/asd492/agentops?logo=docker)](https://hub.docker.com/u/asd492)

---

**Platform:** [agent-circuit-breaker](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-circuit-breaker) ·
[agent-chaos-toolkit](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-chaos-toolkit) ·
[agent-slo-platform](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-slo-platform) ·
[dashboard](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/dashboard) ·
[agent-gateway](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-gateway)

📖 [Documentation](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/) · 🐳 [Docker Hub](https://hub.docker.com/u/asd492)

**Live docs:** [anandhasasidharan.github.io/AgentOps-Agent-System-Operations](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/) · **Live app:** not publicly hosted yet — [run it locally](#-quick-start) or [deploy to Railway](website/docs/railway-deployment.mdx)

</div>

---

## 🔥 Platform Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AgentOps Platform                                │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │   Circuit Breaker │  │   Chaos Toolkit  │  │   SLO Platform   │       │
│  │   :8001           │  │   :8002          │  │   :8000          │       │
│  │                   │  │                   │  │                   │       │
│  │  • DTMC Predictor │  │ • 16 failure     │  │ • OTel ingestion  │       │
│  │  • Graph Monitor  │  │   modes          │  │ • GenAI semconv   │       │
│  │  • PAC Bounds     │  │ • LLM scenario   │  │ • Trust scoring   │       │
│  │  • Z-score Anomaly│  │   proposer       │  │ • SLO evaluation  │       │
│  │  • Policy Engine  │  │ • Closed-loop    │  │ • Burn-rate math  │       │
│  │  • Kill Switch    │  │   refine         │  │ • OWASP/EU AI Act │       │
│  │  • Rollback       │  │ • Resilience     │  │ • Risk budgets    │       │
│  │                   │  │   scoring        │  │                    │       │
│  └────────┬──────────┘  └────────┬─────────┘  └────────┬──────────┘       │
│           │                      │                      │                 │
│           └──────────────────────┼──────────────────────┘                 │
│                                  │                                        │
│                          ┌───────▼────────┐                              │
│                          │   Dashboard    │                              │
│                          │   :8003        │                              │
│                          │   Health +     │                              │
│                          │   Status page  │                              │
│                          └────────────────┘                              │
│                                  │                                        │
│                          ┌───────▼────────┐                              │
│                          │   Gateway      │                              │
│                          │   :8004        │                              │
│                          │   WebSocket    │                              │
│                          │   (NATS → UI)  │                              │
│                          └────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Run locally without Docker

After `make setup`, run `make local-start`. A local `nats-server` is required;
pass its location with `python scripts/run_local.py start --nats-server /path/to/nats-server`.
The launcher uses Python enforcement, persistent SQLite, and private runtime data
under `.agentops-runtime/` (gitignored). This is development mode, not a verified
PostgreSQL production deployment.

Open http://localhost:8003. Log in with any username and the password from
`.agentops-runtime/api-key`. `make local-status` checks processes;
`make local-verify` checks the live stack and creates a demo agent that becomes
locked down after a deliberately failing call. `make local-stop` stops only the
recorded processes and preserves the database and credentials.

Policy `kill` activates the kill switch until release or its configured TTL.
Rollback endpoints prepare pending compensation records; they do not execute
inverse tools. Incidents are marked rolled back only after all records are
confirmed complete. Chaos fault simulations with no observed agent outcome stay
unscored (`unobserved` in summaries), rather than counting as successful tests.

Ratio SLO budgets track observed failures, with rolling-window burn equal to
observed error rate divided by allowed error rate. Default alert multipliers are
1, 2, and 5. Existing explicitly configured thresholds are preserved. Empty
windows return `data_available=false` and do not automatically lock down agents.
Prediction quality and compliance certification are not established by these
runtime checks. The C engine remains experimental; local-start selects Python.

## Dashboard control plane

The dashboard at port 8003 now includes agent registration and inspection, a
searchable execution log, typed policy creation/deletion, kill/release controls,
incident response and pending rollback plans, ratio SLOs and alerts, telemetry
import, chaos simulations/batches, report downloads, and a live event feed.
The server retains the tenant key and proxies allowlisted operations; browser
assets and WebSocket URLs do not contain the raw credential. See the dashboard
page in the documentation for supported actions and explicit operating limits.

## Runnable enforcement example

After `make setup`, run `make guarded-demo`. This starts two temporary localhost
services with SQLite, creates a tenant and policy, permits a safe tool, blocks a
dangerous tool, and verifies fail-closed behavior after stopping the breaker.
No Docker, model credentials, or existing tenant key are required. Processes and
temporary data are cleaned up on exit.

The dashboard now requires authentication: set `API_KEY` to your generated tenant
key and log in using any username and that key as the password. After seeding:

```bash
set -a; . ./.agentops.env; set +a
docker compose up -d --force-recreate dashboard
```

Gateway history requires `X-API-Key`; WebSocket connections require `?api_key=`.
Both deliver only the authenticated tenant's events. `GATEWAY_URL` is the internal server URL. The dashboard bridges WebSocket
events on its own `/ws` route; no public gateway URL or browser API key is needed. Serve production traffic over TLS.

SLOs are evaluated every 30 seconds independently of dashboard requests. Set
`SLO_EVALUATION_INTERVAL_SECONDS=0` to disable the worker. Use the agent UUID
returned by the SLO API consistently in intercept calls and agent-scoped SLOs.
Run one SLO evaluator replica until distributed scheduling is implemented.

Production Compose requires `.env.production` and `DB_PASSWORD`. Load the variables before invoking Compose so interpolation
can read them. URL-encode special characters in database passwords in
`DATABASE_URL`. Container builds and live deployment must be checked on a Docker
host; this example does not establish detector accuracy.

SLO breach events now use file-backed JetStream storage and a durable lockdown
consumer. Compose mounts `nats.conf` and persists data in the `natsdata` volume.
Do not remove this volume when upgrading. Configured NATS must be available at
SLO/CB startup; leaving `NATS_URL` unset explicitly disables event delivery.
Events are acknowledged after lockdown and an event receipt commit together.
Duplicate delivery cannot recreate a policy that an operator has released.
Other event topics remain best-effort notifications.

SLO creation accepts `agent_id`, the UUID returned by `/api/v1/agents`.
The API checks that both that agent and the SLI belong to the caller's tenant.
Use that same UUID in SDK/LangChain intercept calls. Omit the scope only for
an intentionally tenant-wide SLO; a tenant-wide breach cannot target an agent
for automatic lockdown. The SDK supports `create_slo(..., agent_id=agent_id)`.

Telemetry uses the original request's full API key. Rejected exports log
`agentops.telemetry_export_failed` without credentials or input data. Internal
event-driven chaos runs have no raw API key and visibly skip telemetry.

Verify with a local NATS 2.10 server (no Docker required):

```bash
NATS_SERVER_BINARY=/path/to/nats-server make durable-demo
NATS_SERVER_BINARY=/path/to/nats-server make closed-loop-demo
```

The check publishes before a consumer exists, simulates a temporary enforcement
failure, and restarts the broker and consumer using the same storage. CI runs
this check before building images. Storage is bounded to seven days and 1 GiB;
full storage rejects new events. This provides recovery for broker-acknowledged
breaches, not a transactional outbox: a producer crash before acknowledgement
can still lose an event. Receipt retention and schema migration remain follow-up
work; never drop receipts while matching broker messages may be redelivered.

## ⚡ Quick Start

```bash
git clone https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations.git
cd AgentOps-Agent-System-Operations
docker compose up -d
pip install httpx
python scripts/seed.py                # writes .agentops.env with the real key
set -a; . ./.agentops.env; set +a     # export API_KEY
```

Open the dashboard → [http://localhost:8003](http://localhost:8003)

## 📸 Dashboard

> **Screenshot placeholder:** `docs/assets/dashboard.png` — capture it with the commands below, then uncomment the image line in this section.

<!-- ![AgentOps dashboard](docs/assets/dashboard.png) -->

The dashboard aggregates health, SLO status, and circuit-breaker state from the platform services at [http://localhost:8003](http://localhost:8003).

**Capture the screenshot yourself:**

```bash
docker compose up -d          # start the stack
python scripts/seed.py        # populate demo data
./scripts/capture-dashboard.sh
```

`scripts/capture-dashboard.sh` waits for the dashboard to become healthy, seeds demo data if needed, and uses Playwright to write `docs/assets/dashboard.png` at 1440×900. For a GIF, run the same steps and record the browser window, or capture a short video and convert it with `ffmpeg`.

## 🛠️ CLI Quickstart

The CLIs read the seeded key from `$API_KEY`; load it once with:

```bash
set -a; . ./.agentops.env; set +a
```

All three CLIs take the API key via `--api-key` (`-k`) and the service URL via `--base-url` (`-u`). YAML files are **positional arguments** — there is no `-f` flag. `--tenant` is not a valid option on any CLI; use `--api-key`.

```bash
# Circuit Breaker (:8001)
cbctl apply docs/examples/policy.yaml --api-key "$API_KEY"
cbctl policies --api-key "$API_KEY"
cbctl status my-agent --api-key "$API_KEY"

# Chaos Toolkit (:8002)
chaosctl seed --api-key "$API_KEY"
chaosctl run <scenario-id> my-agent --api-key "$API_KEY"
chaosctl report --api-key "$API_KEY"

# SLO Platform (:8000)
sloctl apply docs/examples/slo.yaml --api-key "$API_KEY"
sloctl status --api-key "$API_KEY"
sloctl report owasp --api-key "$API_KEY"
```

> **Note:** `chaosctl` uses a 60-second HTTP client timeout by default, configurable per command with `--timeout`/`-t` or the `CHAOS_TIMEOUT` environment variable. The built-in `llm-timeout` scenario (35 s) completes without extra flags.

## 🌐 Live Demo & Deployment

The **documentation site is live** at [anandhasasidharan.github.io/AgentOps-Agent-System-Operations](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/).

The **application is not publicly hosted** — it is a five-application-service stack backed by Postgres, designed to run locally or in your own cloud account. Both paths are a single command:

```bash
# Local (Docker Compose)
docker compose up -d

# Railway (reads railway.toml, provisions all five application services + Postgres)
railway up
```

See the [Railway Deployment Guide](website/docs/railway-deployment.mdx) for environment variables, health checks, and post-deploy verification.

## 🏗️ Architecture — 5 Application Services

Five application services are built and deployed. Docker Compose additionally runs Postgres, NATS, Prometheus, and Grafana (nine containers total).

| Service | Port | Purpose | Key Features |
|---------|------|---------|--------------|
| **Circuit Breaker** | 8001 | Runtime safety guard | DTMC prediction, graph monitoring, anomaly detection, policy enforcement, kill switch, rollback |
| **Chaos Toolkit** | 8002 | Pre-prod resilience testing | 16 failure modes across LLM/Tool/RAG/MCP, LLM scenario proposer, closed-loop refinement |
| **SLO Platform** | 8000 | Observability & compliance | OTel ingestion, GenAI semantic conventions, trust score, SLO eval, OWASP/EU AI Act |
| **Dashboard** | 8003 | Health aggregation | Real-time status across all services |
| **Gateway** | 8004 | WebSocket bridge | NATS → dashboard real-time updates |

## ✨ What Makes This Different

### Phase A — Predictive Circuit Breaking (DTMC + PAC)
- **DTMC-based risk prediction** — models agent tool-call sequences as a Discrete-Time Markov Chain over tool-risk categories (destructive, execution, data, identity, finance, other)
- **PAC bounds** — confidence bounds accompany model estimates; real-world prediction accuracy has not been established
- **Proactive circuit breaking** — predicts risk _before_ the tool executes, not after

### Phase B — Graph Topology Monitoring
- **Execution graph tracking** — builds a directed graph of agent tool-use sequences in real-time
- **Z-score anomaly detection** — flags structural anomalies when edge weights deviate >2σ from mean
- **Graph factor blending** — anomaly engine weights graph topology at 20% alongside frequency (25%), entropy (20%), reasoning-loop (25%), and timing (10%) detectors

### Phase C — LLM-Based Scenario Proposer
- **Generative scenario discovery** — uses an LLM to propose novel chaos scenarios from agent traces, tenant config, and past experiment data
- **One-shot or interactive** — proposes 3-5 scenarios in a single call, with configurable temperature and max scenarios

### Phase D — Closed-Loop Refinement
- **Critique-based iteration** — refines proposed scenarios through structured LLM critique: feasibility check, coverage analysis, edge case identification
- **Output formatting** — produces production-ready YAML scenario definitions directly

### Phase E — OTel GenAI Semantic Conventions
- **Standardized GenAI metrics** — extracts `gen_ai.usage.*`, `gen_ai.response.*`, and `gen_ai.eval.*` attributes per OpenTelemetry semantic conventions
- **Array value flattening** — handles nested `arrayValue` OTLP fields without data loss
- **Token metrics** — derives prompt/completion/total token SLIs from span attributes

### Phase F — Trust Score Integration
- **VeriAlign trust scoring** — integrates external alignment verification into the observability pipeline
- **Span-level trust attributes** — `gen_ai.eval.trust_score` plus supporting `trust_supported`, `trust_unsupported`, `trust_contradictions`, and `trust_checklist` attributes emitted by the VeriAlign verification object
- **Unified monitoring** — trust scores flow through SLO evaluation alongside traditional SLIs

### Cross-Cutting
- **Per-tenant rate limiting** — in-memory sliding window (60s), configurable via `RATE_LIMIT_RPM`, applied to CB/Chaos/SLO
- **CI/CD pipeline** — test matrix (all 10 packages), clean-venv install, pinned lint/format, then Docker build+push to `asd492/agentops`

## 🧭 Part of the portfolio

AgentOps is the runtime-operations layer of a set of AI-agent infrastructure projects. Each repo is standalone; together they cover the agent lifecycle from identity to interpretability.

| Repo | What it adds | How it connects |
|------|--------------|-----------------|
| [verialign](https://github.com/Anandhasasidharan/verialign) | Verification proxy for LLM output — claim grounding, contradiction detection, confidence scoring | **Wired into this codebase.** Its `gen_ai.eval.trust_*` attributes are ingested by the SLO Platform (Phase F) and evaluated alongside traditional SLIs. |
| [AGENTICU](https://github.com/Anandhasasidharan/AGENTICU) | Multi-agent tracing, MAST failure classification, auto-recovery playbooks | Supplies the trace-level failure taxonomy that AgentOps chaos experiments and SLOs operate on. |
| [agent-reflex](https://github.com/Anandhasasidharan/agent-reflex) | Causal failure attribution and learned recovery strategies | Pairs with the Circuit Breaker: attribution explains why a trip happened, the breaker enforces the response. |
| [SENTRIX](https://github.com/Anandhasasidharan/SENTRIX) | EDR/XDR for agents — capability policy enforced before every tool call | Security-side sibling of the Circuit Breaker policy engine and kill switch. |
| [AGENT-IAM](https://github.com/Anandhasasidharan/AGENT-IAM) | Agent identity and delegation (IBCT/CAT tokens) | Identity layer beneath AgentOps tenant/API-key auth and per-agent policy scoping. |
| [AgentGOV](https://github.com/Anandhasasidharan/AgentGOV) | AI BOMs with EU AI Act, NIST AI RMF, and ISO 42001 crosswalks | Governance evidence layer; complements the SLO Platform's OWASP and EU AI Act checks. |
| [community-ai-audit](https://github.com/Anandhasasidharan/community-ai-audit) | Provider-agnostic model behavior auditing with SIEM export | Turns security findings into telemetry that can feed the same observability pipeline. |
| [probekit-prism](https://github.com/Anandhasasidharan/probekit-prism) | Interpretability infrastructure — SAEs, circuit tracing, probes | Model-level signals that can be exposed as additional eval SLIs. |

> Only **VeriAlign** is integrated in this repository today. The other projects are companions that share the same OpenTelemetry GenAI conventions and agent data model; links describe where they fit rather than shipped integrations.

## 📊 Testing

| Service | Tests | Coverage | Gate | Focus |
|---------|-------|----------|------|-------|
| Circuit Breaker | 88 | 82% | 75% | DTMC, graph monitor, anomaly engine, typed policies, closed loop, API |
| Chaos Toolkit | 63 | 83% | 70% | Scenario proposer, refine, experiments, resilience scoring |
| SLO Platform | 36 | 80% | 80% | OTel extraction, GenAI semconv, SLO evaluation, trust score |
| Dashboard | 1 | — | — | Health aggregation routes |
| Gateway | 8 | — | — | WebSocket bridge, auth |
| Core | 10 | — | — | Rate limiter, seed and docs contracts |
| Events | 11 | — | — | Event models, NATS publisher |
| SDK | 11 | — | — | Client SDK, fail mode |
| LangChain | 10 | — | — | Callback handler, tool wrapper, fail mode |
| Engine | 7 | — | — | Policy blob compiler, Python reference engine |
| **Total** | **245** | — | — | |

```bash
# Run every package's suite
for pkg in agentops-core agent-circuit-breaker agent-chaos-toolkit agent-slo-platform \
           dashboard agent-gateway agentops-events agentops-sdk agentops-langchain; do
  (cd "$pkg" && python -m pytest -x)
done
```

Coverage gates are configured per package in `pyproject.toml` (`--cov-fail-under`).

## 📦 Docker Images

All images hosted on Docker Hub under a single repository:

```bash
# Each service tagged by prefix
asd492/agentops:agent-circuit-breaker-latest
asd492/agentops:agent-chaos-toolkit-latest
asd492/agentops:agent-slo-platform-latest
asd492/agentops:dashboard-latest
asd492/agentops:agent-gateway-latest
```

## 🔧 Tech Stack

| Layer | Choice |
|-------|--------|
| **Language** | Python 3.11+ |
| **API** | FastAPI + Pydantic v2 |
| **Database** | PostgreSQL 16 (async via SQLAlchemy 2.0 + asyncpg) |
| **Telemetry** | OpenTelemetry OTLP (JSON over HTTP) |
| **Predictive** | NumPy (DTMC, PAC bounds, Z-scores) |
| **LLM Integration** | Async LLM calls via httpx (model-agnostic) |
| **CLI** | Typer (`cbctl`, `chaosctl`, `sloctl`) |
| **Auth** | X-API-Key header → tenant lookup |
| **Container** | Docker Compose (multi-service single Dockerfile) |
| **Testing** | pytest + pytest-asyncio + httpx ASGITransport + aiosqlite |
| **CI** | GitHub Actions (test → lint → build+push) |
| **Shared** | `agentops-core` (base models, rate limiter, telemetry) |
| **Events** | `agentops-events` (NATS topics, event models) |

## 🔐 Rate Limiting

Per-tenant in-memory sliding window (60s), applied to Circuit Breaker, Chaos Toolkit, and SLO Platform. `/health` and `/metrics` bypass the limiter.

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_RPM` | `60` | Max requests per minute per tenant |
| `RATE_LIMIT_RPM=0` | — | **Disabled.** No requests are rate-limited. |

## 🌐 Environment Variables

| Variable | Default | Service |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agentops:agentops@localhost:5432/agentops` | All |
| `API_KEY` | `dev-api-key` | Seed tenant slug; seed writes the full `slug:token` key to `.agentops.env` |
| `OTEL_EXPORTER_ENDPOINT` | `http://localhost:8000/v1/traces` | CB, Chaos |
| `RATE_LIMIT_RPM` | `60` | CB, Chaos, SLO |
| `AGENTOPS_FAIL_MODE` | `closed` | SDK, LangChain (safety path) |
| `LOG_LEVEL` | `info` | All |

## 🗺️ Project Structure

```
├── agent-circuit-breaker/     # Phase A+B: DTMC, graph monitor, policy engine
├── agent-chaos-toolkit/       # Phase C+D: LLM scenario proposer, closed-loop refine
├── agent-slo-platform/        # Phase E+F: OTel GenAI semconv, trust score
├── agentops-core/             # Shared: base models, rate limiter, telemetry
├── agentops-events/           # NATS event models + publisher
├── agentops-sdk/              # Python client SDK
├── dashboard/                 # Health aggregation UI
├── agent-gateway/             # WebSocket bridge (NATS → UI)
├── agentops-langchain/        # LangChain integration
├── website/                   # 📖 Docusaurus documentation site
├── monitoring/                # Prometheus config + Grafana dashboards
├── helm/                      # Kubernetes Helm chart
├── terraform/                 # AWS infrastructure as code
├── .github/workflows/         # CI/CD pipeline
├── docs/                      # Design notes, ABI/policy docs, example manifests
├── scripts/seed.py            # Demo data populator
├── scripts/capture-dashboard.sh # Dashboard screenshot capture
├── docker-compose.yml         # Multi-service orchestration
└── Dockerfile                 # Multi-service build (ARG SERVICE)
```

## 📚 Documentation

Full documentation site → [anandhasasidharan.github.io/AgentOps-Agent-System-Operations](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/)

Or build locally:

```bash
cd website
npm install
npm run start
```

## 🧪 Demo

```bash
# Seed the platform; this writes .agentops.env (mode 0600) with the tenant key.
python scripts/seed.py
set -a; . ./.agentops.env; set +a

# Verify circuit breaker
curl -s http://localhost:8001/api/v1/tool-calls -H "X-API-Key: $API_KEY" | python -m json.tool

# List configured SLOs
curl -s http://localhost:8000/api/v1/slos -H "X-API-Key: $API_KEY" | python -m json.tool

# Check resilience score
curl -s http://localhost:8002/api/v1/resilience-score -H "X-API-Key: $API_KEY" | python -m json.tool
```

## 📄 License

MIT

---

<div align="center">
  <sub>Built with ❤️ for safe, reliable, observable AI agents</sub>
</div>
