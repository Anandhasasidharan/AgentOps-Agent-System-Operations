"""Fail-mode policy for safety-path decisions.

AgentOps is a safety product, so the default when the Circuit Breaker cannot be
reached is to deny (fail closed). Operators can explicitly opt into availability
over protection with ``AGENTOPS_FAIL_MODE=open``.

Every degraded decision emits a structured JSON log event named
``agentops.degraded_decision`` so it can be alerted on.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

FAIL_CLOSED = "closed"
FAIL_OPEN = "open"
VALID_FAIL_MODES = {FAIL_CLOSED, FAIL_OPEN}
DEFAULT_FAIL_MODE = FAIL_CLOSED

_logger = logging.getLogger(__name__)


def resolve_fail_mode(explicit: str | None = None) -> str:
    """Resolve the fail mode from an explicit value, env var, or default.

    Invalid values fail closed rather than allowing traffic by accident.
    """

    raw = explicit if explicit is not None else os.environ.get("AGENTOPS_FAIL_MODE")
    if raw is None:
        return DEFAULT_FAIL_MODE
    mode = str(raw).strip().lower()
    if mode not in VALID_FAIL_MODES:
        _logger.warning(
            "invalid AGENTOPS_FAIL_MODE %r; defaulting to %s",
            raw,
            DEFAULT_FAIL_MODE,
        )
        return DEFAULT_FAIL_MODE
    return mode


def log_degraded_decision(
    *,
    service: str,
    operation: str,
    fail_mode: str,
    reason: str,
    agent_id: str | None = None,
    tool_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one structured, alertable log event for a degraded decision."""

    event: dict[str, Any] = {
        "event": "agentops.degraded_decision",
        "service": service,
        "operation": operation,
        "fail_mode": fail_mode,
        "decision": "block" if fail_mode == FAIL_CLOSED else "allow",
        "reason": reason,
    }
    if agent_id is not None:
        event["agent_id"] = agent_id
    if tool_name is not None:
        event["tool_name"] = tool_name
    if extra:
        event.update(extra)
    _logger.warning(json.dumps(event, default=str, sort_keys=True))
