"""Tools target — inject failures into tool calls.

Failure modes:
  - timeout: Tool call hangs/times out
  - crash: Tool returns internal error / crash
  - bad_output: Tool returns malformed or unexpected output
  - wrong_data: Tool returns incorrect data
"""

from __future__ import annotations

import asyncio
import random
from typing import Any


FAILURE_MODES = ["timeout", "crash", "bad_output", "wrong_data"]


async def inject_tool_fault(
    config: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failure_mode = config.get("failure_mode", "timeout")
    params = config.get("params", {})

    if failure_mode == "timeout":
        return await _simulate_tool_timeout(params)
    elif failure_mode == "crash":
        return _simulate_tool_crash(params)
    elif failure_mode == "bad_output":
        return _simulate_bad_output(params)
    elif failure_mode == "wrong_data":
        return _simulate_wrong_data(params)
    else:
        raise ValueError(f"Unknown tool failure mode: {failure_mode}")


async def _simulate_tool_timeout(params: dict[str, Any]) -> dict[str, Any]:
    delay = params.get("delay_seconds", random.uniform(25, 120))
    await asyncio.sleep(delay)
    return {
        "fault_injected": True,
        "failure_mode": "timeout",
        "error": f"Tool call timed out after {delay:.1f}s",
        "simulated_delay_s": delay,
    }


def _simulate_tool_crash(params: dict[str, Any]) -> dict[str, Any]:
    error_type = params.get("error_type", "InternalServerError")
    error_message = params.get(
        "error_message",
        "An unexpected error occurred while processing the tool call."
    )
    return {
        "fault_injected": True,
        "failure_mode": "crash",
        "error": f"{error_type}: {error_message}",
        "status_code": params.get("status_code", 500),
    }


def _simulate_bad_output(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "bad_output",
        "output": params.get(
            "output",
            {"error": "null", "result": None, "status": "failed"}
        ),
        "message": "Tool returned malformed or unexpected output",
    }


def _simulate_wrong_data(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "wrong_data",
        "output": params.get(
            "output",
            {"data": [], "total": 0, "message": "No records found"}
        ),
        "message": "Tool returned incorrect/empty data",
    }
