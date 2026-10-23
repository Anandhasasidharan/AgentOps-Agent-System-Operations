"""Python binding to the C engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from ._cext import ffi, lib
except Exception as exc:  # pragma: no cover - makes import error clear
    raise ImportError(
        "agentops_engine._cext is not built. Run: pip install -e agentops-engine/"
    ) from exc

from .pyengine import AoCall, AoResult


@dataclass
class CEngine:
    _engine: Any = None

    def __post_init__(self) -> None:
        cfg = ffi.new("ao_config *")
        cfg.max_agents = 1024
        cfg.max_state_bytes = 16 * 1024 * 1024
        cfg.fail_open = 0
        p = ffi.new("ao_engine **")
        rc = lib.ao_engine_new(cfg, p)
        if rc != 0 or p[0] == ffi.NULL:
            raise RuntimeError(f"ao_engine_new failed: {rc}")
        self._engine = p[0]

    def load_policy(self, compiled: bytes) -> None:
        rc = lib.ao_policy_load(self._engine, compiled, len(compiled))
        if rc != 0:
            raise ValueError(f"ao_policy_load failed: {rc}")

    def intercept(self, call: AoCall) -> AoResult:
        out = ffi.new("ao_result *")
        c = ffi.new("ao_call *")
        c.agent_id = call.agent_id.encode()
        c.agent_id_len = len(c.agent_id)
        c.tool = call.tool.encode()
        c.tool_len = len(c.tool)
        c.input = call.input.encode() if call.input else ffi.NULL
        c.input_len = len(call.input.encode()) if call.input else 0
        c.tokens = call.tokens
        c.cost_micro = call.cost_micro
        c.now_ns = call.now_ns
        c.minute_of_day = call.minute_of_day
        c.weekday = call.weekday
        c.risk_score_micro = call.risk_score_micro
        c.anomaly_score_micro = call.anomaly_score_micro
        rc = lib.ao_intercept(self._engine, c, out)
        if rc != 0:
            raise RuntimeError(f"ao_intercept failed: {rc}")
        return AoResult(
            verdict=int(out.verdict),
            reason_code=int(out.reason_code),
            policy_index=int(out.policy_index),
            retry_after_ms=int(out.retry_after_ms),
        )

    def close(self) -> None:
        if self._engine is not None:
            lib.ao_engine_free(self._engine)
            self._engine = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
