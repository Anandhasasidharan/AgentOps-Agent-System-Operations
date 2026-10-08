# Policy Semantics

Source of truth: `agent-circuit-breaker/src/circuit_breaker/policy_engine.py` and `agent-circuit-breaker/src/circuit_breaker/models.py`.

## Common evaluation
- Policies are loaded for a tenant where `enabled=True`, ordered by `Policy.priority` descending.
- The first matching policy decides the call. `tool_allowlist` matches unknown tools and returns block; exact matches in the allowlist do not block.
- `action` values: `allow`, `block`, `reroute`, `kill`, `alert`.
- If no policy matches, default verdict is allow.
- `ToolCall.risk_score` / `anomaly_score` are expected to be in `[0, 1]` in normal use, but the engine compares raw values.

## Blocklist
- `conditions.tools`: list of tool-name patterns.
- Uses Python `fnmatch.fnmatch`, which is OS-case-normalized; on Linux it is effectively case-sensitive.
- If any pattern matches `tool_name`, policy matches and blocks.

## Allowlist
- `conditions.tools`: list of allowed tools.
- If a pattern matches `tool_name`, `_matches_policy` returns `False` and the policy does not block.
- If `tool_name` is not in the list, policy matches and blocks.
- Existing behavior oddity: glob matches in an allowlist do not explicitly allow; they merely avoid the block path.

## Rate limit
- `conditions.max_calls`: integer.
- Policy matches when `max_calls > 0` and `windowed_stats.call_count >= max_calls`.
- Boundary: inclusive.

## Token budget
- `conditions.max_tokens`: integer.
- Policy matches when `max_tokens > 0` and `windowed_stats.total_tokens >= max_tokens`.
- Boundary: inclusive.

## Risk / anomaly thresholds
- `conditions.max_risk_score` / `conditions.max_anomaly_score`.
- Policy matches when score is present and strictly greater than threshold.

## Time window
- `conditions.start` / `conditions.end`: float hours.
- Current hour is `now.hour + now.minute / 60` using wall-clock UTC.
- Policy matches when `start <= current_hour <= end`.
- Cross-midnight windows are not specially handled.

## Reasoning loop
- `conditions.max_consecutive_same_tool`: integer, default 5.
- Policy matches when `windowed_stats.consecutive_same_tool >= max_consecutive_same_tool`.

## Reason strings
- Deterministic base: policy name/type and blocked tool.
- Additional type-specific suffixes are emitted for each policy type.
