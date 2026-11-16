"""Fail-mode policy for the LangChain adapter.

Mirrors ``agentops.fail_mode`` so the adapter keeps its small dependency
surface (httpx only). The default is fail closed; ``AGENTOPS_FAIL_MODE=open``
is the explicit availability-over-protection override.
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
