# MEMORY.md

## Agent Zero Memory — AgentOps Project Timeline

```mermaid
flowchart LR
  A[Idea: AgentOps] --> B[Core services scaffolded]
  B --> C[Tests + coverage]
  C --> D[Auth/API key model]
  D --> E[Rate limiting]
  E --> F[NATS events]
  F --> G[Phase A: DTMC]
  G --> H[Phase B: Graph monitor]
  H --> I[Phase C/D: LLM proposer + refine]
  I --> J[Phase E/F: OTel GenAI + trust score]
  J --> K[CI/CD fixed]
  K --> L[Docker Hub pushes]
  L --> M[Docs site]
  M --> N[Railway/prod compose]
  N --> O[Alignment/interpretability analysis]
```

## 1. Initial Scaffold
- Created 5 service packages with `src/` layout:
  - `agent-circuit-breaker/`
  - `agent-chaos-toolkit/`
  - `agent-slo-platform/`
  - `dashboard/`
  - `agent-gateway/`
- Shared libraries:
  - `agentops-core/`
  - `agentops-events/`
  - `agentops-sdk/`
  - `agentops-langchain/`
- Root `Dockerfile`, `docker-compose.yml`, `Makefile`, `pyproject.toml`

## 2. Quality Standard
- Tests use SQLite in-memory: `aiosqlite:///:memory:`
- Coverage thresholds:
  - Circuit Breaker: 75%
  - Chaos: 70%
  - SLO: 80%
- `pytest` with asyncio mode auto
- `respx` for HTTP mocks

## 3. Auth Model
- API key format: `slug:random-hex-token`
- Sent via `X-API-Key`
- Key split on `:` to extract slug
- Stored hash in `Tenant.api_key_hash`
- Gateway uses `?api_key=` for WebSocket auth

## 4. Rate Limiting
- Per-tenant in-memory sliding window, 60s
- `RATE_LIMIT_RPM` default 60, `0` disables
- Bypasses `/health` and `/metrics`

## 5. Events
- `agentops-events` package
- 6 NATS topics
- `publish_event()` with retry
- Optional NATS; no-op publisher when unavailable

## 6. Phase A — DTMC Predictor
- Added `circuit_breaker/dtmc.py`
- `predictor.py`: `get_prediction()`, `compute_proactive_risk()`
- PAC bounds for approximate risk prediction
- Exposed `/predict` endpoint

## 7. Phase B — Graph Monitor
- Added `circuit_breaker/graph_monitor.py`
- `ExecutionGraph` records tool-call sequences
- Z-score anomaly detection
- Anomaly engine blends graph factor at 0.20
- `/graph/status`, `/graph/anomalies`

## 8. Phase C/D — LLM Proposer + Refine
- Added `chaos_toolkit/scenario_proposer.py`
- `propose_scenarios()` builds context/prompt/calls LLM
- `refine_proposals()` critiques proposals
- `/scenarios/propose`, `/scenarios/refine`
- `ProposeRequest`, `ProposeResponse`, `ProposedScenario`

## 9. Phase E/F — OTel GenAI + Trust Score
- SLO `extractor.py`:
  - GenAI attributes
  - arrayValue flattening
  - trust score extraction
- SLO `receiver.py`: derives token/trust metrics
- VeriAlign:
  - `otel_genai.py`: trust score params
  - `main.py`: plumbed trust score from verification
  - `trust_scorer.py`: consistency, factuality, safety, instruction-following

## 10. CI/CD
- `.github/workflows/agentops.yml`
- test → lint → build
- Removed Terraform/Helm/smoke jobs
- Docker Hub credential secrets added
- Image repo flattened to `asd492/agentops`

## 11. Docs
- Rewrote README with dynamic shields and Phase A–F coverage
- Added Docusaurus site in `website/`
- Docs: overview, architecture, services, DTMC, graph monitor, scenario proposer, OTel GenAI, trust score, deployment, rate limiting, CI/CD, API reference
- GitHub Pages deploy workflow

## 12. Deployment Prep
- `railway.toml`
- `docker-compose.prod.yml`
- `.env.production`
- `nats.conf`
- `website/docs/railway-deployment.mdx`

## 13. Alignment / Interpretability Analysis
- Project has practical trust scoring and safety interception
- No true mechanistic interpretability
- Industry uses Langfuse, LangSmith, Datadog, Arize, Braintrust, Galileo, Fiddler, NVIDIA, Splunk
- Research leaders: Anthropic, Google DeepMind ASAT, OpenAI
- Plan: integrate with OTel/GenAI, LangChain/CrewAI, Langfuse/Datadog, document industry gap

## Project Explanation (From User Notes)
AgentOps is a safety and observability platform for AI agents. When an AI agent can write code, send emails, call APIs, or delete files, the risks are:
1. catastrophic tool calls such as `rm -rf /`, secret leaks, or overspending
2. silent failure from hallucinated tool calls or crashed external APIs
3. missing metrics, SLOs, and compliance evidence

The platform fixes these through five services:
- Circuit Breaker :8001 — risk scoring, DTMC prediction, graph monitoring, anomaly detection, kill switch, rollback, policies
- Chaos Toolkit :8002 — 16 failure modes, 15 scenarios, LLM proposer, closed-loop refine, resilience scoring, CI reports
- SLO Platform :8000 — OTel ingestion, GenAI semconv, SLO evaluation, trust score, OWASP/EU AI Act
- Dashboard :8003 — health view
- Gateway :8004 — NATS to WebSocket

Current built status:
- Circuit Breaker: intercept pipeline, DTMC, graph monitor, anomaly engine, 16 endpoints, rate limiting, 36 tests, 75% coverage
- Chaos Toolkit: 16 failure modes, 15 scenarios, experiment runner, resilience scoring, LLM proposer, refinement, reports, 30 tests, 70% coverage
- SLO Platform: OTel ingestion, SLI extraction, SLOs, alerts, GenAI semconv, trust score, compliance, 24 tests, 80% coverage
- Shared: agentops-core, agentops-events, agentops-sdk, rate limiting
- Dashboard/Gateway: implemented
- Infra: GitHub Actions, Docker Hub, Docusaurus docs live, Terraform/Helm removed, Railway not deployed

Remaining to make full platform:
- Deploy PostgreSQL and 5 services
- Expose dashboard publicly
- Optional NATS server
- Optional .env.example/Railway variable filling
- Optional custom domain/Grafana links
- Optional VeriAlign proxy live trust scoring

## Current State
- Code complete
- 90 tests passing
- CI/CD operational
- Docker images pushed
- Docs live via GitHub Pages
- Not publicly deployed unless Railway is run
