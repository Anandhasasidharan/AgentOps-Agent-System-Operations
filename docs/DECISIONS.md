# Decisions

- Default engine remains Python in this phase.
- The C contract uses integer-only policy semantics wherever possible.
- Existing Python `time_window` semantics use wall-clock UTC and inclusive float hours; Phase 1 C evaluates against `minute_of_day` and `weekday` supplied by Python.
- Rate-limit state resets on policy load because per-agent counters are owned by the C engine and policy swap clears bounded state.
- **Policy conditions are typed.** `circuit_breaker.policy_conditions` is the single source of truth for both `POST /api/v1/policies` and `cbctl apply`. Unknown keys are rejected with 422 instead of creating a policy that silently never matches. Cross-midnight time windows are rejected rather than accepted and never matching.
- **Policies can be scoped to one agent** with the optional `agent_id` condition. Existing policies without it remain tenant-wide. Auto-lockdown uses this scope so an SLO breach for one agent does not stop every agent in the tenant.
- **SLO auto-lockdown blocks immediately.** A breach creates a priority-100 `tool_blocklist` policy with `{"tools": ["*"], "agent_id": "<agent>"}`. A rate-limit policy was considered, but the closed-loop contract says the next intercept is blocked; a rate limit would allow more calls first.
- **Fail closed is the default.** `AGENTOPS_FAIL_MODE` accepts `closed` (default) or `open`. Adapters deny when the Circuit Breaker is unreachable, times out, returns a non-2xx response, or returns a malformed verdict. `open` is the explicit availability-over-protection override and is documented as such. Every degraded decision emits a structured `agentops.degraded_decision` log event.
- **The LangChain fail-open tests were intentionally changed.** They encoded the pre-M1 behavior that contradicted the safety contract. The replacement tests assert closed-by-default and an explicit `open` override.
