# ABI

ABI version: `AO_ABI_VERSION 1`.

- C never calls `time()`. Callers supply `now_ns`.
- No heap allocation inside `ao_intercept`. All state is in pools sized during `ao_engine_new`.
- `fail_open=0` means engine-limit returns `AO_BLOCK` with reason `ENGINE_LIMIT`.
- Agent state is sharded by `agent_id` hash; one lock per shard.
- `ao_policy_load` swaps the active policy blob and resets per-agent counters.
- Thread safety: reads and writes are guarded by per-shard locks; policy swap uses a reader/writer lock.
- All errors are status codes. No function aborts or calls `exit`.

## Blob format

Little-endian:

```text
magic "AOPL" | u16 version | u16 flags | u32 total_len | u32 crc32
u32 policy_count
repeat policy: u8 type | u8 action | u16 reserved | u32 body_len | body
strings: u16 len + bytes (no NUL)
```

Caps enforced by both compiler and loader:
- max 256 policies
- max 64 patterns per policy
- max pattern length 256 bytes
- max rate-limit count 4096
- max window 24h

The loader must validate `total_len`, `crc32`, every `body_len`, and all string lengths with overflow checks.
