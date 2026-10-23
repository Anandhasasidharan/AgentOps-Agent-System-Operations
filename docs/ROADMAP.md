# AgentOps: Roadmap to a True Platform

Priority-ordered, sequenced by dependency, not by attractiveness. Every milestone ships something a reviewer can verify. Later milestones assume earlier ones are real.

Companion documents: [`FEATURES.md`](FEATURES.md) (what exists and what is broken) and [`PLAN.md`](PLAN.md) (tasks, estimates, acceptance evidence, working loop).

Last updated 2026-10-23.

---

## The thesis

AgentOps does not have a features problem. It has a **verification** problem.

It already ships a policy engine, DTMC prediction, anomaly detection, chaos testing, SLO evaluation, and a native-engine experiment. What it cannot yet do is prove any of it works outside the happy path, or that a stranger can run it. Four examples:

- The flagship closed-loop feature, where an SLO breach tightens policy, has never fired. The writer uses `max_calls_per_minute` and the reader uses `max_calls`. No test covers the seam.
- The safety adapters **fail open**. When the circuit breaker is unreachable, the tool call proceeds, so protection disappears when the network is unhealthy.
- A fresh install fails: an unpinned SQLAlchemy resolves to a version that no longer installs `greenlet`, and CI does not run a clean-install job to catch it.
- Nothing measures whether the detectors actually catch attacks. The roadmap this one replaces checked correctness and speed, but never detection quality.

A reviewer's first question about a safety platform is "what happens when it's wrong?" Today the honest answer is "nothing, silently." So the first milestones are not warm-up. They are the product.

---

## Definition of "true platform" (v1.0)

Summarized here, with evidence for each item in `PLAN.md`.

1. A fresh clone installs and all tests pass in CI, including a clean-venv job.
2. Every package with tests runs in CI.
3. Every feature marked ✅ has a test that fails if the feature is removed.
4. The SLO-breach to auto-lockdown to blocked-call loop is proven by one end-to-end test.
5. All adapters fail closed by default, with a tested override.
6. The quickstart works on a clean machine in 10 minutes.
7. A public demo is running.
8. Detection rate, false-positive rate, and latency are published with method and seed.
9. The native engine matches Python on 10k random traces and passes sanitizers and fuzzing.
10. Dashboard, gateway, and Grafana require auth; no default keys in prod compose.
11. Schema changes go through migrations in every DB-owning service.
12. An audit log records policy changes, kills, and incident resolutions.
13. Packages are on PyPI, images are tagged, a changelog and GitHub release exist.
14. The README makes no claim without a test, endpoint, or benchmark behind it.

---

## Releases

| Release | Contents | Character |
|---|---|---|
| **v0.9 "Real"** | M0 to M4, then R1 | Public, usable, measured. No native engine |
| **v1.0 "Fast and hardened"** | M5, M6, then R2 | Embedded native engine plus security and operations baseline |

Stopping at v0.9 still yields a strong, honest, public project.

---

## Milestones

### M0: Baseline

Push the engine branch, turn every 🔴 and important 🟡 row of `FEATURES.md` into labeled GitHub issues, and reproduce the four reported defects (`sloctl` 500, `chaosctl` timeout, `RATE_LIMIT_RPM=0`, `seed.py` commands).

**Exit:** branch visible, issue list exists, each defect reproduced or closed.

### M1: Make the existing claims true

No new capability. Every advertised feature starts working, and a test proves it.

- **Condition schemas.** Fix the lockdown writer. Replace `conditions: dict[str, Any]` with a typed model per policy type, reject unknown keys with 422, and make one schema the single source of truth for both the API and `cbctl apply`. One test per policy type proving a misspelled key is rejected.
- **Closed-loop test.** Publish a synthetic `agentops.slo.breach.*` event, assert a policy appears, assert the next intercept is blocked. This is the most valuable test in the repository.
- **Fail mode.** `AGENTOPS_FAIL_MODE=open|closed`, default `closed`, applied in the SDK and the LangChain adapter. A structured, alertable log event on every degraded decision. Document the availability-versus-protection tradeoff in `DECISIONS.md`.
- **CI honesty.** Add dashboard, gateway, langchain, and engine tests to the matrix. Pin `sqlalchemy[asyncio]>=2.0,<2.2`. Pin `ruff` and `black`. Add a brand-new-virtualenv job that installs everything and runs all tests.
- **Four defects fixed**, each with a regression test.
- **Paper trail.** Replace hand-written test counts with a CI badge, correct stale docs, add `LICENSE`, ignore build artifacts, move planning docs to `docs/`, resolve `helm/` and `terraform/`, rename `.env.production` to an example file.

**Exit:** from a clean clone, every package's tests pass, lint is clean at the pinned versions, the closed-loop test passes, and the PR's Actions run is green.

### M2: Runs for real

- A quickstart in `examples/` using a scripted tool-calling agent that needs no API key, with one dangerous tool.
- `make demo`: SLO breach, auto-lockdown, blocked call.
- A public deployment on a single VPS using the prod compose. Fix the asyncpg `DATABASE_URL`, mount `nats.conf`, add TLS, read secrets from the environment. Require auth on the gateway and lock down Grafana first, since the demo is exposed. Delete `railway.toml` or verify it with a real deploy.
- README rewrite with quickstart, GIF of the full loop, screenshot, and a link to the honest status table. GitHub description and topics.

**Exit:** someone who has never seen the repo follows the README on a clean machine and sees a block within 10 minutes (timed). The public URL responds.

### M3: Adapters and failure behavior

- Bounded intercept timeout, with behavior on timeout set by the fail mode.
- `Idempotency-Key` support, so retries do not double-count or double-block.
- **MCP proxy.** MCP is the emerging interop layer, and the chaos toolkit already models `mcp` as a target. Every MCP client becomes a potential user.
- OpenAI Agents SDK adapter.
- LangChain and SDK hardening: fail mode, timeouts, retries, connection pooling.
- Check whether incidents are persisted independent of NATS publishing. If so, document events as notifications. If not, add at-least-once delivery with consumer-side dedupe.

**Exit:** three agent setups in `examples/` (LangChain, OpenAI Agents SDK, MCP) are protected. Stopping the breaker blocks calls by default in each. Contract tests cover every adapter.

### M4: Prove it

- Seeded trace generator: benign traffic, destructive commands, injection-driven calls, runaway loops, bursts.
- Replay harness comparing an allowlist-only baseline, the policy engine, plus anomaly, plus graph, plus DTMC, and all layers. Report detection rate per attack class, false-positive rate on benign traffic, and latency.
- Review `dtmc.py` and reword "PAC guarantee" to what the math supports.
- Publish `docs/BENCHMARKS.md` and a README table. Record a pinned-machine latency baseline, engine-only versus end to end.

**Exit:** `make bench` regenerates the tables from the seed, and every performance or detection claim in the README cites them.

### R1: Release v0.9

PyPI packages for the SDK and adapters, tagged images, changelog, GitHub release, and the claim audit.

### M5: Native engine

The engine already exists on the branch, reportedly uncommitted and untested. This milestone finishes and verifies it. Scope for v1.0 is the **policy engine only**; risk, anomaly, DTMC, and graph stay in Python.

- **Gate G1** first (below).
- Commit the engine, move the function-local import in `proxy.py` to module level.
- Differential testing: Hypothesis-generated policies and traces, identical verdicts from `PyEngine` and `CEngine`, with explicit seeds for documented edge cases (inclusive boundaries, time windows, glob versus exact, priority ties).
- Resolve parity gaps (`retry_after_ms`, state keying): fix or document each as intended.
- C hygiene: single input encode, `-Wall -Wextra -Werror`, ASan and UBSan CI job, libFuzzer on the policy loader and intercept.
- **Embedded mode:** the SDK loads the engine in-process, pulls policies from the server on an interval, and obeys the fail mode.
- Wheels via `cibuildwheel` (manylinux x86_64 and aarch64, macOS).
- Benchmarks: Python versus C engine-only, embedded versus server end to end.

**Exit:** differential suite green on 10k traces, sanitizer and fuzz jobs green, a prebuilt wheel installs, benchmark table published.

### M6: Hardening and operability

- **Security.** Required auth on dashboard and gateway, no anonymous Grafana Admin, no dev keys in compose defaults, configurable PII redaction on `tool_input` before storage.
- **Migrations.** Alembic for Circuit Breaker and Chaos Toolkit. Remove `create_all` at startup from all three services. Tests for empty-to-head and previous-to-head upgrades.
- **Operability.** Health checks that probe the database and NATS, correlation IDs across services, gateway moved to `lifespan`.
- **Audit log.** Append-only record of policy create, update, and delete, kill-switch activation, and incident resolution, with actor, timestamp, and before/after diff, plus a read API. It pairs naturally with the existing `Incident` model and is cheap to build and hard to fake.
- **Chaos injection.** Bounded, configurable async delays instead of long sleeps inside a request.
- **Typing and matrix.** mypy strict on the shared packages first, then the services in stages. Python 3.12 and 3.13 in the matrix.
- Stretch: `POST /api/v1/policies/simulate`, replaying recent calls against a candidate policy to show what would have been blocked.

**Exit:** definition-of-done items 10, 11, and 12 pass.

### R2: Release v1.0

Final claim audit, changelog, docs site update, tag, GitHub release, PyPI publish.

---

## Decision gates

| Gate | Question | Decided by |
|---|---|---|
| G1 | Is the native engine worth building, and in what shape? | M4 latency baseline. The audit's figures (about 35k calls/s engine-only against about 731 end to end) put evaluation near 2% of a request. If that holds, build embedded mode as the point of M5 and do not expect much server-path speedup |
| G2 | Which detectors stay on by default? | M4 results against the allowlist baseline. Keep what earns its place, publish the rest honestly |
| G3 | Hosted offering, or self-host only? | Adoption signals after R1. The default answer is self-host only |

---

## Standing rules

- **No claim without a test.** Every ✅ row has a test that fails if the feature is removed.
- **No benchmark without a method.** Record host, commit, seed, trace, and call count.
- **No marketing without an endpoint.** If the README lists it, `curl` reaches it. This is how trust score and risk budgets ended up advertised and unreachable.
- **Every documented limitation gets a test asserting it**, so limitations stay honest. This covers the oddities in `POLICY_SEMANTICS.md`: allowlist glob only avoids the block path, inclusive boundaries, no cross-midnight windows.
- **Fail closed by default** for anything on the safety path.
- **Never edit an existing test to make it pass.**
- **Every status report pastes real command output.**
- One milestone in progress at a time. Every PR updates the `FEATURES.md` rows it touches.

---

## Sequencing rationale

M1 before everything, because a faster engine on top of a dead feature is a faster wrong answer, and because an install that fails stops all review. M2 and M3 before M4 so there is something real to measure and every adapter targets a verified core. M4 before M5 so the native engine is justified by data, not by taste. M6 after M5 so hardening covers the final architecture. The control-plane UI, RBAC, and measured compliance come after v1.0 because they are the most visible and the least load-bearing.

---

## Risks

| Risk | Mitigation |
|---|---|
| The native engine yields little end-to-end speedup | Gate G1 and embedded mode as the real goal |
| Scope grows during M1 | No new features until M1 is done |
| mypy strict floods M6 | Stage it, shared packages first |
| Public demo gets abused | Demo tenant, rate limits, required auth on gateway and dashboard |
| Detectors fail to beat the allowlist baseline | Publish that honestly, drop losers from defaults (G2) |
| Dependency drift breaks fresh installs again | Upper bounds plus the clean-venv CI job |
| Estimates are off | Reassess and rescale at the end of M1 |

---

## Deferred beyond v1.0

RBAC and SSO, approval workflow with a real `reroute` target, full control-plane UI with policy versioning and rollback, measured compliance evidence, agent-side chaos adapter, native port of the risk, anomaly, DTMC, and graph modules, TypeScript SDK, Anthropic, LangGraph, and CrewAI adapters, data retention and erasure, per-service databases, load and soak testing, alert delivery (Slack, PagerDuty, webhook).

If time is short, **M0 to M4 alone** yield a defensible story: a policy layer that fails closed, is proven by tests, runs publicly, and is measured against a baseline. That is a stronger claim than a dozen half-working features.
