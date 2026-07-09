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
[![Tests](https://img.shields.io/badge/tests-90%20passing-22BA5A?logo=pytest)](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/actions)
[![Docker Pulls](https://img.shields.io/docker/pulls/asd492/agentops?logo=docker)](https://hub.docker.com/u/asd492)

---

**Platform:** [agent-circuit-breaker](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-circuit-breaker) ·
[agent-chaos-toolkit](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-chaos-toolkit) ·
[agent-slo-platform](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-slo-platform) ·
[dashboard](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/dashboard) ·
[agent-gateway](https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations/tree/main/agent-gateway)

📖 [Full Documentation](https://anandhasasidharan.github.io/AgentOps-Agent-System-Operations/)

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

## ⚡ Quick Start

```bash
git clone https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations.git
cd AgentOps-Agent-System-Operations
docker compose up -d
pip install httpx && python scripts/seed.py
```

Open the dashboard → [http://localhost:8003](http://localhost:8003)

## 🏗️ Architecture — 5 Services

| Service | Port | Purpose | Key Features |
|---------|------|---------|--------------|
| **Circuit Breaker** | 8001 | Runtime safety guard | DTMC prediction, graph monitoring, anomaly detection, policy enforcement, kill switch, rollback |
| **Chaos Toolkit** | 8002 | Pre-prod resilience testing | 16 failure modes across LLM/Tool/RAG/MCP, LLM scenario proposer, closed-loop refinement |
| **SLO Platform** | 8000 | Observability & compliance | OTel ingestion, GenAI semantic conventions, trust score, SLO eval, OWASP/EU AI Act |
| **Dashboard** | 8003 | Health aggregation | Real-time status across all services |
| **Gateway** | 8004 | WebSocket bridge | NATS → dashboard real-time updates |

## ✨ What Makes This Different

### Phase A — Predictive Circuit Breaking (DTMC + PAC)
- **DTMC-based risk prediction** — models agent tool-call sequences as a Discrete-Time Markov Chain with 5 states (Idle, Low, Medium, High, Critical)
- **PAC bounds** — Probably Approximately Correct bounds guarantee prediction accuracy with confidence intervals
- **Proactive circuit breaking** — predicts risk _before_ the tool executes, not after

### Phase B — Graph Topology Monitoring
- **Execution graph tracking** — builds a directed graph of agent tool-use sequences in real-time
- **Z-score anomaly detection** — flags structural anomalies when edge weights deviate >2σ from mean
- **Graph factor blending** — anomaly engine weights graph topology at 20% alongside frequency, entropy, and timing detectors

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
- **Span-level trust attributes** — `gen_ai.eval.trust_score` with component breakdown (consistency, factuality, safety, instruction following)
- **Unified monitoring** — trust scores flow through SLO evaluation alongside traditional SLIs

### Cross-Cutting
- **Per-tenant rate limiting** — in-memory sliding window (60s), configurable via `RATE_LIMIT_RPM`, applied to CB/Chaos/SLO
- **CI/CD pipeline** — 3 jobs (test 5-matrix → lint → Docker build+push to `asd492/agentops`)

## 📊 Testing

| Service | Tests | Coverage | Focus |
|---------|-------|----------|-------|
| Circuit Breaker | 36 | 75%+ | DTMC, graph monitor, anomaly engine, policies, API |
| Chaos Toolkit | 30 | 70%+ | Scenario proposer, refine, experiments, resilience scoring |
| SLO Platform | 24 | 80%+ | OTel extraction, GenAI semconv, SLO evaluation, trust score |
| **Total** | **90** | — | |

```bash
# Run all tests
cd agent-circuit-breaker && python -m pytest -x && cd ..
cd agent-chaos-toolkit  && python -m pytest -x && cd ..
cd agent-slo-platform   && python -m pytest -x && cd ..
```

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
| `RATE_LIMIT_RPM=0` | disabled | Disable rate limiting entirely |

## 🌐 Environment Variables

| Variable | Default | Service |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agentops:agentops@localhost:5432/agentops` | All |
| `API_KEY` | `dev-api-key` | Auth (tenant slug) |
| `OTEL_EXPORTER_ENDPOINT` | `http://localhost:8000/v1/traces` | CB, Chaos |
| `RATE_LIMIT_RPM` | `60` | CB, Chaos, SLO |
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
├── scripts/seed.py            # Demo data populator
├── docker-compose.yml         # Multi-service orchestration
└── Dockerfile                 # Multi-service build (ARG SERVICE)
```

## 📚 Documentation

Full documentation site → [agentops-docs.vercel.app](https://agentops-docs.vercel.app) _(coming soon)_

Or build locally:

```bash
cd website
npm install
npm run start
```

## 🧪 Demo

```bash
# Seed the platform with demo data
python scripts/seed.py

# Verify circuit breaker
curl -s http://localhost:8001/api/v1/tool-calls -H "X-API-Key: dev-api-key" | python -m json.tool

# Check SLO compliance
curl -s http://localhost:8000/api/v1/status -H "X-API-Key: dev-api-key" | python -m json.tool

# Check resilience score
curl -s http://localhost:8002/api/v1/resilience-score -H "X-API-Key: dev-api-key" | python -m json.tool
```

## 📄 License

MIT

---

<div align="center">
  <sub>Built with ❤️ for safe, reliable, observable AI agents</sub>
</div>
