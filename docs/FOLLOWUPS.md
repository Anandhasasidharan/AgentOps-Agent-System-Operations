# Followups

- `railway.toml` was not audited in this prompt.
- Phase 1 does not implement risk scoring, anomaly stats, DTMC, graph monitor, wheels, MCP proxy, deployment, or dashboard features.
- The C engine currently mirrors policy semantics; risk/anomaly engines should be specified before C parity is attempted.
- `helm/` and `terraform/` remain optional, unmanaged examples. Neither is in CI. Pick one as the supported deployment path at M2.3 or delete both.
- Native-engine parity gaps remain (`retry_after_ms`, state keying, time-window edge cases) and are M5 work, not M1.
- `agentops-engine` is not in `make setup`; it is optional until M5. The clean-install CI job does install it.
- The gateway still uses deprecated `@app.on_event`; move to lifespan in M6.3.
- `/health` does not probe Postgres or NATS; M6.3.
