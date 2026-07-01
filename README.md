# AgentOps — AI Agent Safety & Observability Platform

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1)](https://postgresql.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> Four integrated services for operating AI agents safely, reliably, and at scale.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentOps Platform                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Circuit        │  Chaos          │  SLO                    │
│  Breaker        │  Toolkit        │  Platform               │
│  :8001          │  :8002          │  :8000                  │
│                 │                 │                         │
│  • Intercept    │  • 16 failure   │  • OTel span ingestion  │
│  • Policy       │    modes        │  • SLO evaluation       │
│    enforcement  │  • 15 built-in  │  • Burn-rate maths      │
│  • Kill switch  │    scenarios    │  • OWASP/EU AI Act      │
│  • Anomaly      │  • Resilience   │  • Risk budgets         │
│    detection    │    scoring      │                         │
└────────┬────────┴────────┬────────┴───────────┬─────────────┘
         │                 │                    │
         └─────────────────┼────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Dashboard  │
                    │  :8003      │
                    │             │
                    │  • Health   │
                    │    summary  │
                    │  • Status   │
                    │    page     │
                    └─────────────┘
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| **Language** | Python 3.11+ |
| **API** | FastAPI + Pydantic v2 |
| **Database** | PostgreSQL 16 (async via SQLAlchemy 2.0 + asyncpg) |
| **Telemetry** | OpenTelemetry OTLP (JSON over HTTP) |
| **CLI** | Typer (3 CLIs: `cbctl`, `chaosctl`, `sloctl`) |
| **Auth** | X-API-Key header → tenant lookup (shared across services) |
| **Container** | Docker Compose (multi-service single build) |
| **Testing** | pytest + pytest-asyncio + httpx + aiosqlite |
| **CI** | GitHub Actions (JUnit reports via Chaos Toolkit) |
| **Shared** | `agentops-core` — Base, TimestampMixin, Auth, Telemetry helpers |

## Quick Start

```bash
# Clone and launch all services + PostgreSQL
git clone https://github.com/Anandhasasidharan/AgentOps-Agent-System-Operations.git
cd AgentOps-Agent-System-Operations
docker compose up
```

Wait for all 4 services to report healthy, then seed demo data:

```bash
pip install httpx   # if not already installed
python scripts/seed.py
```

Open the dashboard: [http://localhost:8003](http://localhost:8003)

## Demo Walkthrough

The seed script populates the platform with:

1. **Tenant** `acme-corp` (slug = API key `dev-api-key`)
2. **Agent** `demo-agent` running LangChain + OpenAI
3. **SLO** — 95% task success rate over 30-day rolling window
4. **Circuit Breaker Policy** — blocks filesystem-destructive commands (`rm -rf /`, `dd`, `mkfs`, etc.)
5. **Chaos Scenarios** — 12 built-in failure modes seeded
6. **Safe tool call** — `read_file` is allowed through
7. **Blocked tool call** — `rm` is intercepted and blocked
8. **OTel spans** — ingested by SLO platform for metrics

### Verify

```bash
# Check circuit breaker policy blocked a dangerous call
curl -s http://localhost:8001/api/v1/tool-calls\
  -H "X-API-Key: dev-api-key" | python -m json.tool

# Check SLO compliance
curl -s http://localhost:8000/api/v1/status\
  -H "X-API-Key: dev-api-key" | python -m json.tool

# Check chaos resilience score
curl -s http://localhost:8002/api/v1/resilience-score\
  -H "X-API-Key: dev-api-key" | python -m json.tool
```

## CLI Tools

Each service ships with a CLI:

```bash
# Circuit Breaker
cbctl apply policy.yaml          # Apply YAML policies
cbctl status                     # Show circuit breaker state

# Chaos Toolkit
chaosctl seed                    # Seed built-in scenarios
chaosctl run <scenario-id>       # Run a chaos experiment
chaosctl report                  # Generate resilience report

# SLO Platform
sloctl apply slo.yaml            # Apply SLO definitions from YAML
sloctl status                    # Show SLO compliance status

# All CLIs accept --api-key (default: dev-api-key)
```

## Local Development

```bash
# Install each service (with dev dependencies)
pip install -e agentops-core/
pip install -e agent-circuit-breaker/[dev]
pip install -e agent-chaos-toolkit/[dev]
pip install -e agent-slo-platform/[dev]
pip install -e dashboard/[dev]

# Run tests per service
cd agent-circuit-breaker && python -m pytest
cd agent-chaos-toolkit  && python -m pytest
cd agent-slo-platform   && python -m pytest
```

## Testing

| Service | Tests | Coverage | Key areas |
|---------|-------|----------|-----------|
| Circuit Breaker | 40 | 78% | Policy engine, anomaly detection, kill switch, OTel emission |
| Chaos Toolkit | 48 | 77% | 16 failure modes, 15 scenarios, resilience scoring, CI reporters |
| SLO Platform | 33 | 83% | SLO eval, burn-rate math, risk budgets, OWASP/EU AI Act compliance |
| Dashboard | 1 | — | Health aggregation |

```bash
# Run all test suites
cd agent-circuit-breaker && python -m pytest && cd ..
cd agent-chaos-toolkit  && python -m pytest && cd ..
cd agent-slo-platform   && python -m pytest && cd ..
```

## Environment Variables

| Variable | Default | Service |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agentops:agentops@localhost:5432/agentops` | All |
| `API_KEY` | `dev-api-key` | Auth (tenant slug) |
| `OTEL_EXPORTER_ENDPOINT` | `http://localhost:8000/v1/traces` | CB, Chaos |
| `CB_URL` | `http://localhost:8001` | Dashboard |
| `CHAOS_URL` | `http://localhost:8002` | Dashboard |
| `SLO_URL` | `http://localhost:8000` | Dashboard |
| `LOG_LEVEL` | `info` | All |

## Deployment

### Local (Docker Compose)

```bash
docker compose up -d
docker compose logs -f
python scripts/seed.py
```

### AWS (Terraform)

Provision the full stack on AWS ECS Fargate + RDS + ALB:

```bash
# 0. Prerequisites: AWS credentials, container images pushed to ECR/Docker Hub
# 1. Bootstrap remote state backend
bash scripts/bootstrap-terraform.sh

# 2. Deploy infrastructure
cd terraform
terraform init
terraform plan -var="db_password=<your-password>"
terraform apply -var="db_password=<your-password>"
```

Architecture:

```
Internet → ALB (port 8000-8003)
              ├── 8000 → SLO Platform (Fargate)
              ├── 8001 → Circuit Breaker (Fargate)
              ├── 8002 → Chaos Toolkit (Fargate)
              └── 8003 → Dashboard (Fargate)

All services → RDS PostgreSQL (private subnet)
ALB health checks → /health on each service
```

See `terraform/` for the full configuration (12 files, ~300 lines).

## Project Structure

```
├── agentops-core/              # Shared library (Base, Auth, Telemetry)
├── agent-circuit-breaker/      # Policy enforcement + anomaly detection
├── agent-chaos-toolkit/        # Failure injection + resilience testing
├── agent-slo-platform/         # SLO evaluation + compliance reporting
├── dashboard/                  # Health aggregation UI
├── scripts/seed.py             # Demo data populator
├── scripts/bootstrap-terraform.sh   # Terraform remote state bootstrap
├── terraform/                  # AWS infrastructure as code (VPC, ALB, ECS, RDS)
├── docker-compose.yml          # Multi-service orchestration
├── Dockerfile                  # Multi-service build (ARG SERVICE)
├── pyproject.toml              # Root tool config
└── .env.example                # Environment reference
```
