# Domain 1: AgentOps — Agent System Operations

> **Academic foundation:** Wang et al. *"A Survey on AgentOps"* (arXiv 2508.02121, Aug 2025) — first comprehensive survey defining AgentOps as a field.
> **Market signal:** 47% of GitHub issues in multi-agent frameworks are bugs/operational stability, NOT agent behavior.
> **Stanford HAI 2026:** 362 documented AI incidents (+55% YoY). "Responsible AI is not keeping pace."
> **Dario Amodei:** AGI-level systems by 2026-2027. Every company deploying agents needs AgentOps NOW.
> **Bottom line:** DevOps in 2011. Kubernetes doesn't exist yet for AI agents. Green field.

---

## Competitive Landscape

| Project | Stars | What it does | Gap |
|---|---|---|---|
| **AgentOps-AI/agentops** | ~5k | Python SDK + dashboard for agent monitoring, cost tracking | Commercial-first, observability only |
| **Azure/agentops** | ~500 | Microsoft AgentOps Accelerator — CI/CD evals + observability | Azure/Foundry-tied |
| **boshu2/agentops** | ~200 | Local `.agents/` bookkeeping for coding agents | Coding-agents only, Markdown |
| **Langfuse** | 29.7k | Traces + evals + prompt mgmt | Observability only, not full ops |
| **Pydantic Logfire** | ~5k | Python-native agent observability | Observability only |
| **Arize Phoenix** | 10.2k | OpenTelemetry-native tracing + evals | Observability + eval, not ops |

**Key takeaway:** The AgentOps survey defines 4 stages: Monitoring → Anomaly Detection → Root Cause Analysis → Resolution. Tools exist for stages 1-2. Stages 3-4 (RCA + automated remediation) have ZERO production OSS tools.

---

## Project 1A: Agent Circuit Breaker — Runtime Safety Kill Switch

**Recruitability:** 🔥🔥🔥🔥🔥
**Build time:** 2-3 weeks
**Technologies:** Python, FastAPI, MCP middleware, OpenTelemetry, statistical anomaly detection, PostgreSQL

### What It Does

A lightweight proxy that monitors agent behavior in real-time and **automatically halts** agents when they deviate from expected patterns. Think "PagerDuty incident response, but executed by machines in milliseconds, not humans in minutes."

### Why This Exists

The *Internal Safety Collapse* paper (arXiv 2603.23509) proved that **ALL frontier models** produce harmful content as a side effect of normal professional tasks — no adversarial prompting needed. Stanford HAI 2026: 362 incidents. Guardrails AI and NeMo Guardrails only check chat output text — they don't catch tool-call-level anomalies. Microsoft AGT has circuit breakers but is a 7-package monorepo.

### Core Features

1. **Tool-call anomaly detection:** Monitor MCP tool invocations for unusual patterns — repeated failed calls, calls outside scope, access pattern shifts
2. **Behavioral drift detection:** Track token usage distribution, response latency, action sequences. Alert on statistical deviation from baseline
3. **Three-tier response:** (a) Log-only, (b) Route to safer model, (c) Hard kill + human escalation
4. **Framework-agnostic proxy:** Works with OpenAI Agents, LangChain, CrewAI, AutoGen, and raw MCP through a single middleware layer
5. **Playbook engine:** User-defined rules — "If agent calls delete_* API more than 3 times in 60s → HARD_KILL"

### Architecture

```
Agent → Circuit Breaker Proxy → LLM / Tools
              │
              ├─ Anomaly Detector (statistical models)
              ├─ Policy Engine (user-defined rules)
              ├─ Response Engine (log/route/kill)
              └─ Audit Log (every decision timestamped)
```

### Competitive Moat

- Guardrails AI / NeMo: **chat text only.** Agent Circuit Breaker = **tool-call level.**
- Microsoft AGT: **heavy, enterprise.** Agent Circuit Breaker = **pip install, 5 lines of config.**
- AgentOps-AI: **observability only.** Agent Circuit Breaker = **observability → action.**

### Monetization

1. **OSS Core:** MIT license, self-hosted, single-agent free
2. **Pro:** Multi-agent, custom anomaly models, Slack/PagerDuty integration — $49/seat/mo
3. **Enterprise:** On-prem, compliance reports (EU AI Act, SOC 2), SLA guarantees, dedicated playbook library

---

## Project 1B: Agent SLO Platform — Reliability Engineering for AI

**Recruitability:** 🔥🔥🔥🔥
**Build time:** 3-4 weeks
**Technologies:** Python, OpenTelemetry, Prometheus, Grafana, YAML, PostgreSQL

### What It Does

Define, measure, and alert on Service Level Objectives **specific to AI agents** — not generic infra metrics but agent-native signals like hallucination rate, task success rate, tool call accuracy, and cost-per-task.

### Why This Exists

SRE has SLOs for APIs (latency, error rate, throughput). MLOps has model accuracy, data drift. **AgentOps has nothing.** Every company deploying agents is blind to whether their agents are getting better or worse. The AgentOps survey identifies monitoring as phase 1 but provides no standardized metric framework.

### Core Features

1. **Agent-native metrics:** Task success rate, hallucination rate, tool accuracy, cost-per-task, avg. steps-to-completion, human escalation rate
2. **SLO definition language:** YAML-based — `task_success_rate > 95% over 7d rolling window`
3. **Burn rate alerts:** Error budget consumption tracking. Alert at 2%, page at 5%, emergency at 10%
4. **Multi-tenant dashboards:** Per-team, per-agent, per-environment SLO status
5. **OpenTelemetry-native:** Consume traces from Langfuse, Phoenix, or direct OTel pipeline

### Competitive Moat

- Datadog/Dynatrace: **infra metrics, not agent behavior.**
- Langfuse/Phoenix: **observability, not reliability engineering.**
- **Agent SLO Platform = first tool that bridges SRE discipline to agent systems.**

### Monetization

1. **OSS Core:** Single-team, single-agent SLO definitions, basic alerting
2. **Pro:** Multi-team, historical analysis, custom metric SDK — $39/seat/mo
3. **Enterprise:** Compliance reporting (EU AI Act audit trail), SSO, SLA guarantees

---

## Project 1C: Agent Chaos Toolkit — Resilience Testing for AI Agents

**Recruitability:** 🔥🔥🔥🔥
**Build time:** 2-3 weeks
**Technologies:** Python, fault injection framework, Docker, MCP, pytest

### What It Does

Chaos Monkey for AI agents. Inject controlled failures (tool timeouts, bad RAG results, model degradation, MCP server crashes) and measure how agents recover. Prove your agents are resilient before production.

### Why This Exists

Netflix Chaos Monkey proved that systems fail in production, so test failure in staging. AI agents have MORE failure modes than microservices (hallucination, tool misuse, reasoning loops, context corruption) but NO chaos engineering tool exists for them.

### Core Features

1. **Failure injection catalog:** Tool timeout, corrupted RAG results, model degradation (swap gpt-4o → gpt-4o-mini mid-run), MCP server crash, context window pressure
2. **Experiment definition:** YAML-based — define agent under test, failure scenarios, success criteria
3. **Resilience scoring:** Per-agent resilience score across failure categories
4. **CI/CD integration:** GitHub Action — `chaos test ./agent-config.yaml` in every PR
5. **Regression detection:** Did an agent update make it MORE fragile?

### Competitive Moat

- Nobody does this. Zero competitors. **Category creation.**
- Complements Agent Circuit Breaker — chaos toolkit finds weaknesses, circuit breaker stops them in production.

### Monetization

1. **OSS Core:** Python library, CLI, local mode
2. **Pro:** CI/CD integration, team dashboards, historical trends — $29/seat/mo
3. **Enterprise:** Custom failure scenarios, compliance certification, dedicated resilience audits

---

## Build Order

| Priority | Project | Effort | Impact | Reason |
|---|---|---|---|---|
| **1** | Agent Circuit Breaker | 2-3 weeks | 🔥🔥🔥🔥🔥 | Everyone deploying agents needs this NOW. Stanford HAI confirms urgency. |
| **2** | Agent Chaos Toolkit | 2-3 weeks | 🔥🔥🔥🔥🔥 | Category creation. Pair with Circuit Breaker for complete reliability story. |
| **3** | Agent SLO Platform | 3-4 weeks | 🔥🔥🔥🔥 | Natural follow-on. Needs Circuit Breaker data to feed SLO metrics. |

---

## Why This Domain Wins

1. **Just defined by academics** — Wang et al. (Aug 2025): *"research on the operations of agent systems is sparse."*
2. **Massive real-world validation** — 47% of framework issues are operational, not agent-logic.
3. **Stanford HAI confirms urgency** — 362 incidents, up 55% YoY.
4. **Amodei's timeline** — AGI by 2027 means everyone needs this within 18 months.
5. **Zero dominant OSS** — Build the Kubernetes of AI agents. First mover owns the category.
