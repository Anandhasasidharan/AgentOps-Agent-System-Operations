"""Compile validated policy definitions into the AgentOps policy blob."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Any, Iterable

from circuit_breaker.yaml_policy import PolicyYaml, parse_yaml

MAGIC = b"AOPL"
VERSION = 1

MAX_POLICIES = 256
MAX_PATTERNS_PER_POLICY = 64
MAX_PATTERN_LEN = 256
MAX_RATE_LIMITS = 4096
MAX_WINDOW_SECONDS = 24 * 60 * 60

_TYPE_IDS = {
    "tool_allowlist": 1,
    "tool_blocklist": 2,
    "rate_limit": 3,
    "token_budget": 4,
    "risk_threshold": 5,
    "anomaly_threshold": 6,
    "time_window": 7,
    "reasoning_loop": 8,
}
_ACTION_IDS = {"allow": 0, "block": 1, "reroute": 2, "kill": 3, "alert": 4}


@dataclass
class CompiledPolicy:
    policy_type: str
    action_id: int
    body: bytes


class PolicyCompileError(ValueError):
    pass


def _patterns(patterns: Iterable[Any]) -> list[str]:
    pats = list(patterns or [])
    if len(pats) > MAX_PATTERNS_PER_POLICY:
        raise PolicyCompileError("too many patterns")
    return [str(p) for p in pats]


def _body_for(spec: Any) -> tuple[int, bytes]:
    typ = _TYPE_IDS[spec.policy_type]
    conds = spec.conditions or {}
    if spec.policy_type in {"tool_allowlist", "tool_blocklist"}:
        patterns = _patterns(conds.get("tools", []))
        parts = [struct.pack("<H", len(patterns))]
        for p in patterns:
            b = p.encode("utf-8")
            if len(b) > MAX_PATTERN_LEN:
                raise PolicyCompileError("pattern too long")
            parts.append(struct.pack("<H", len(b)))
            parts.append(b)
        return typ, b"".join(parts)
    if spec.policy_type == "rate_limit":
        max_calls = int(conds.get("max_calls") or 0)
        window = int(conds.get("window_seconds") or 3600)
        if max_calls > MAX_RATE_LIMITS:
            raise PolicyCompileError("too many rate limits")
        if window > MAX_WINDOW_SECONDS:
            raise PolicyCompileError("window too large")
        return typ, struct.pack("<II", max_calls, window)
    if spec.policy_type == "token_budget":
        max_tokens = int(conds.get("max_tokens") or 0)
        window = int(conds.get("window_seconds") or 3600)
        if window > MAX_WINDOW_SECONDS:
            raise PolicyCompileError("window too large")
        return typ, struct.pack("<II", max_tokens, window)
    if spec.policy_type == "risk_threshold":
        max_risk = float(conds.get("max_risk_score") or 1.0)
        return typ, struct.pack("<Q", int(max_risk * 1_000_000))
    if spec.policy_type == "anomaly_threshold":
        max_anomaly = float(conds.get("max_anomaly_score") or 1.0)
        return typ, struct.pack("<Q", int(max_anomaly * 1_000_000))
    if spec.policy_type == "time_window":
        start = float(conds.get("start") or 0)
        end = float(conds.get("end") or 24)
        if start < 0 or end > 24 or start > end:
            raise PolicyCompileError("invalid time window")
        return typ, struct.pack("<II", int(start * 60), int(end * 60))
    if spec.policy_type == "reasoning_loop":
        max_same = int(conds.get("max_consecutive_same_tool") or 5)
        return typ, struct.pack("<I", max_same)
    raise PolicyCompileError(f"unsupported type {spec.policy_type}")


def compile_policy_yaml(content: str) -> bytes:
    docs = parse_yaml(content)
    if len(docs) > MAX_POLICIES:
        raise PolicyCompileError("too many policies")
    policies = []
    for doc in docs:
        if not doc.spec.enabled:
            continue
        action_id = _ACTION_IDS.get(doc.spec.action.action)
        if action_id is None:
            raise PolicyCompileError(f"bad action {doc.spec.action.action}")
        typ, body = _body_for(doc.spec)
        policies.append(struct.pack("<BBH", typ, action_id, 0) + struct.pack("<I", len(body)) + body)
    body = b"".join(policies)
    total_len = 12 + 4 + len(body)
    header = MAGIC + struct.pack("<HHII", VERSION, 0, total_len, 0)
    data = header + struct.pack("<I", len(policies)) + body
    crc = zlib.crc32(data[:8] + data[12:]) & 0xFFFFFFFF
    data = data[:8] + struct.pack("<I", crc) + data[12:]
    return data


def parse_blob(blob: bytes) -> list[tuple[int, int, bytes]]:
    if len(blob) < 16 or blob[:4] != MAGIC:
        raise PolicyCompileError("bad magic")
    version, flags, total_len, crc = struct.unpack_from("<HHII", blob, 4)
    if version != VERSION or flags != 0 or total_len != len(blob):
        raise PolicyCompileError("bad header")
    if (zlib.crc32(blob[:8] + blob[12:]) & 0xFFFFFFFF) != crc:
        raise PolicyCompileError("bad crc")
    count, = struct.unpack_from("<I", blob, 16)
    pos = 20
    out = []
    for _ in range(count):
        typ, action, reserved = struct.unpack_from("<BBH", blob, pos)
        body_len, = struct.unpack_from("<I", blob, pos + 4)
        pos += 8
        body = blob[pos : pos + body_len]
        if len(body) != body_len:
            raise PolicyCompileError("truncated body")
        out.append((typ, action, body))
        pos += body_len
    if pos != len(blob):
        raise PolicyCompileError("trailing bytes")
    return out
