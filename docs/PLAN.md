# AgentOps: Plan

Companion to [`ROADMAP.md`](ROADMAP.md) (what and why) and [`FEATURES.md`](FEATURES.md)
(honest status). This file holds the working plan: tasks, estimates, acceptance
evidence, and the loop every change follows.

Last updated: 2026-10-23. Estimates are engineer-days for one person.

---

## Working loop

1. Pick the first unfinished task in the current milestone. Do not skip ahead.
2. Create a branch named `feat/m<N>-<name>`.
3. Write the failing test first where the bug or claim allows it.
4. Make the smallest change that passes. No unrelated refactors.
5. Run the touched package's suite, then the clean-install command below.
6. Run `make lint` and `make format-check`.
7. Update the `FEATURES.md` rows and this file's evidence block in the same PR.
8. Commit one logical step at a time with a conventional message.

Acceptance commands for every task:

```bash
# Touched package
cd <package> && python -m pytest -x

# Every package (after the pinned install)
make test
cd agentops-engine && python -m pytest -x   # requires agent-circuit-breaker installed

# Static checks at the pinned versions
make lint
make format-check
```

---

## M0: Baseline (in progress)

| # | Task | Est. | Acceptance | Status |
|---|---|---|---|---|
| M0.1 | Commit the native-engine work to `feature/c-policy-engine` | 0.5 | Branch contains the engine files, no build artifacts | Done locally; branch not pushed |
| M0.2 | Turn every 🔴 / important 🟡 row into a labeled issue | 0.5 | Issue list matches FEATURES.md | Follow-up (needs GitHub access) |
| M0.3 | Reproduce `sloctl` 500, `chaosctl` timeout, `RATE_LIMIT_RPM=0`, `seed.py` commands | 0.5 | Four regression tests exist and pass | Done: `93277cd`, `7c17c19`, `13c21d9`, `c55af60` |

**Exit:** branch visible; issue list exists; each defect reproduced or closed.

---

## M1: Make the existing claims true

| # | Task | Est. | Acceptance evidence | Status |
|---|---|---|---|---|
| M1.1 | Typed condition schemas for all 8 policy types; one source of truth for API and `cbctl apply`; reject unknown keys with 422 | 2 | `tests/integration/test_policy_schema.py` — one misspelled key per type, API and YAML | Done |
| M1.2 | Closed-loop test: SLO breach → auto-lockdown policy → next intercept blocked | 1 | `tests/integration/test_closed_loop.py`; SLO breach event carries `agent_id` in `test_breach_event.py` | Done |
| M1.3 | `AGENTOPS_FAIL_MODE=open\|closed`, default `closed`, in SDK and LangChain; structured degraded-decision log | 1.5 | `agentops-sdk/tests/test_fail_mode.py`; `agentops-langchain/tests/test_handler.py` | Done |
| M1.4 | CI honesty: all packages in matrix, pinned SQLAlchemy, pinned lint tools, clean-venv job | 1.5 | `.github/workflows/agentops.yml`; `make test`; `make lint` | Done |
| M1.5 | Four M0 defects fixed with regressions | 0.5 | Existing regression tests green | Done (commit list in M0.3) |
| M1.6 | Paper trail: CI badge, stale docs, LICENSE, ignores, examples, helm/terraform decision | 1 | README badge, `docs/AGENTS.md`, `docs/FEATURES.md`, `.gitignore` | Partly done; helm/terraform decision recorded in FOLLOWUPS |

**Exit:** clean clone installs; every package's tests pass in CI; lint and format
are clean at pinned versions; the closed-loop test passes; the PR is green.

---

## M2: Runs for real

| # | Task | Est. | Acceptance |
|---|---|---|---|
| M2.1 | Keyless scripted tool-calling quickstart in `examples/` with one dangerous tool | 2 | Example blocks the dangerous tool from a clean checkout |
| M2.2 | `make demo`: breach, lockdown, blocked call | 1 | Demo exits non-zero on failure and prints the blocked verdict |
| M2.3 | Public deployment: TLS, secrets from env, gateway/dashboard auth, Grafana locked down | 3 | Public URL responds; unauthenticated gateway/dashboard requests are rejected |
| M2.4 | README rewrite with quickstart, GIF, screenshot, status table | 1 | Timed clean-machine run under 10 minutes |

---

## M3: Adapters and failure behavior

| # | Task | Est. | Acceptance |
|---|---|---|---|
| M3.1 | Bounded intercept timeout, behavior follows fail mode | 1 | Timeout test in SDK and adapter |
| M3.2 | `Idempotency-Key` support | 1.5 | Retried intercept does not double-count or double-block |
| M3.3 | MCP proxy | 3 | An MCP client is protected by the normal intercept pipeline |
| M3.4 | OpenAI Agents SDK adapter | 2 | Contract test covers allow, block, unavailable |
| M3.5 | SDK/LangChain hardening: retries, pooling, configurable timeout | 1.5 | Tests for retry and timeout |
| M3.6 | NATS delivery: at-least-once with consumer dedupe, or document notifications | 1.5 | Persistence test independent of publish |

---

## M4: Prove it

| # | Task | Est. | Acceptance |
|---|---|---|---|
| M4.1 | Seeded trace generator (benign, destructive, injection, loops, bursts) | 2 | `make bench` regenerates the seed deterministically |
| M4.2 | Replay harness vs allowlist baseline, with per-class detection, false positives, latency | 3 | `docs/BENCHMARKS.md` generated from one command |
| M4.3 | Review `dtmc.py` and reword the PAC claim | 0.5 | Wording matches the math; test asserts the bound |
| M4.4 | README table cites benchmarks | 0.5 | Every performance/detection claim links to a row |

---

## R1: Release v0.9

| # | Task | Est. | Acceptance |
|---|---|---|---|
| R1.1 | PyPI packages for SDK and adapters | 2 | `pip install agentops-sdk` from a clean venv |
| R1.2 | Tagged images, changelog, GitHub release | 1 | Release links images and changelog |
| R1.3 | Final claim audit | 1 | Every README claim has a test, endpoint, or benchmark |

---

## M5: Native engine

| # | Task | Est. | Acceptance |
|---|---|---|---|
| M5.0 | Gate G1: decide embedded mode from M4 latency data | 0.5 | Written decision in DECISIONS.md |
| M5.1 | Differential tests: Python vs C on generated policies/traces | 3 | 10k traces, identical verdicts |
| M5.2 | Resolve `retry_after_ms` and state-keying parity | 1 | Fixed or documented per case |
| M5.3 | ASan, UBSan, libFuzzer jobs | 2 | CI jobs green on parser and intercept |
| M5.4 | Embedded in-process mode with policy pull and fail mode | 3 | Adapter uses embedded engine; fail-mode tests pass |
| M5.5 | `cibuildwheel` wheels | 1.5 | Prebuilt wheel installs on Linux x86_64/aarch64 and macOS |
| M5.6 | Engine benchmarks | 1 | Python vs C and embedded vs server published |

---

## M6: Hardening and operability

| # | Task | Est. | Acceptance |
|---|---|---|---|
| M6.1 | Required auth on dashboard/gateway; no anonymous Grafana admin; PII redaction | 2 | Unauthenticated requests rejected; redaction test |
| M6.2 | Alembic migrations in all DB services; remove `create_all` | 3 | Empty-to-head and previous-to-head upgrade tests |
| M6.3 | DB/NATS health probes, correlation IDs, gateway lifespan | 2 | Health fails when DB is down; one trace has one correlation ID |
| M6.4 | Append-only audit log with read API | 2 | Policy change, kill, and resolution each produce an audit row |
| M6.5 | Bounded async chaos delays | 1.5 | No long sleep inside a request; timeout test |
| M6.6 | mypy strict staging; Python 3.12/3.13 matrix | 3 | CI jobs green per package |

---

## R2: Release v1.0

Final claim audit, changelog, docs site update, tag, GitHub release, PyPI
publish.

---

## Risks and reassessment

The roadmap's risk table applies. Reassess estimates at the end of M1: the
native-engine and clean-install work are the two most likely to move. If time is
short, M0–M4 is the defensible release; stop there rather than starting M5.

---

## Evidence log

Paste real command output here when a milestone closes. Never write a test count
that was not observed in the same session.

```text
2026-10-23  M1 verification (local, Python 3.12.3)
  agentops-core         10 passed
  agentops-events       11 passed
  agent-circuit-breaker 88 passed, 81.58% coverage (gate 75%)
  agent-chaos-toolkit   63 passed, 82.91% coverage (gate 70%)
  agent-slo-platform    36 passed, 80.38% coverage (gate 80%)
  dashboard              1 passed
  agent-gateway          8 passed (4 deprecation warnings)
  agentops-sdk          11 passed
  agentops-langchain    10 passed
  agentops-engine        7 passed
  ruff 0.16.10          All checks passed
  black 26.10.0        83 files would be left unchanged
```
