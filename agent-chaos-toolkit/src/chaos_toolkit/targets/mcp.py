"""MCP target — inject failures into MCP server interactions.

Failure modes:
  - server_down: MCP server unreachable
  - timeout: MCP request times out
  - bad_capabilities: Server reports wrong capabilities
  - auth_failure: Authentication/authorization failure
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

FAILURE_MODES = ["server_down", "timeout", "bad_capabilities", "auth_failure"]


async def inject_mcp_fault(
    config: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failure_mode = config.get("failure_mode", "server_down")
    params = config.get("params", {})

    if failure_mode == "server_down":
        return _simulate_server_down(params)
    elif failure_mode == "timeout":
        return await _simulate_mcp_timeout(params)
    elif failure_mode == "bad_capabilities":
        return _simulate_bad_capabilities(params)
    elif failure_mode == "auth_failure":
        return _simulate_auth_failure(params)
    else:
        raise ValueError(f"Unknown MCP failure mode: {failure_mode}")


def _simulate_server_down(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "server_down",
        "error": "Connection refused: MCP server at mcp://tools.example.com:8443 is unreachable",
        "status_code": 502,
        "message": "MCP server is down or unreachable",
    }


async def _simulate_mcp_timeout(params: dict[str, Any]) -> dict[str, Any]:
    delay = params.get("delay_seconds", random.uniform(30, 90))
    await asyncio.sleep(delay)
    return {
        "fault_injected": True,
        "failure_mode": "timeout",
        "error": f"MCP request timed out after {delay:.1f}s",
        "simulated_delay_s": delay,
    }


def _simulate_bad_capabilities(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "bad_capabilities",
        "claimed_capabilities": params.get(
            "claimed_capabilities", ["read_file", "execute_shell", "delete_database"]
        ),
        "actual_capabilities": ["read_file"],
        "message": "MCP server claimed capabilities it does not support",
    }


def _simulate_auth_failure(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "auth_failure",
        "error": params.get("error_message", "Authentication failed: invalid or expired API key"),
        "status_code": 401,
        "message": "MCP server rejected authentication",
    }
