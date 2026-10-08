# Decisions

- Default engine remains Python in this phase.
- The C contract uses integer-only policy semantics wherever possible.
- Existing Python `time_window` semantics use wall-clock UTC and inclusive float hours; Phase 1 C evaluates against `minute_of_day` and `weekday` supplied by Python.
- Rate-limit state resets on policy load because per-agent counters are owned by the C engine and policy swap clears bounded state.
