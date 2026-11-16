"""Fail-mode behavior for the Python SDK.

The Circuit Breaker is on the safety path. When it cannot be reached the SDK
must deny by default (fail closed), and only allow when the operator explicitly
sets ``AGENTOPS_FAIL_MODE=open``.
"""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from agentops import AgentOpsSDK, AgentOpsUnavailableError


def _degraded_events(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "agentops.degraded_decision" in record.getMessage()
    ]


@pytest.mark.asyncio
@respx.mock
async def test_intercept_fails_closed_by_default(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENTOPS_FAIL_MODE", raising=False)
    respx.post("http://localhost:8001/v1/intercept").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    sdk = AgentOpsSDK(api_key="test-key")
    caplog.set_level(logging.WARNING, logger="agentops.fail_mode")

    with pytest.raises(AgentOpsUnavailableError):
        await sdk.intercept(agent_id="agent-1", tool_name="rm", tool_input={})

    events = _degraded_events(caplog)
    assert any('"fail_mode": "closed"' in event for event in events)
    assert any('"decision": "block"' in event for event in events)
    await sdk.close()


@pytest.mark.asyncio
@respx.mock
async def test_intercept_can_explicitly_fail_open(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENTOPS_FAIL_MODE", raising=False)
    respx.post("http://localhost:8001/v1/intercept").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    sdk = AgentOpsSDK(api_key="test-key", fail_mode="open")
    caplog.set_level(logging.WARNING, logger="agentops.fail_mode")

    result = await sdk.intercept(agent_id="agent-1", tool_name="rm", tool_input={})

    assert result["allowed"] is True
    assert result["degraded"] is True
    events = _degraded_events(caplog)
    assert any('"fail_mode": "open"' in event for event in events)
    assert any('"decision": "allow"' in event for event in events)
    await sdk.close()


@pytest.mark.asyncio
@respx.mock
async def test_intercept_reads_fail_mode_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTOPS_FAIL_MODE", "open")
    respx.post("http://localhost:8001/v1/intercept").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    sdk = AgentOpsSDK(api_key="test-key")
    result = await sdk.intercept(agent_id="agent-1", tool_name="rm", tool_input={})
    assert result["degraded"] is True
    await sdk.close()


@pytest.mark.asyncio
@respx.mock
async def test_intercept_fails_closed_on_server_error() -> None:
    respx.post("http://localhost:8001/v1/intercept").respond(500, json={"detail": "boom"})
    sdk = AgentOpsSDK(api_key="test-key")
    with pytest.raises(AgentOpsUnavailableError):
        await sdk.intercept(agent_id="agent-1", tool_name="rm", tool_input={})
    await sdk.close()


@pytest.mark.asyncio
@respx.mock
async def test_intercept_fails_closed_on_malformed_response() -> None:
    respx.post("http://localhost:8001/v1/intercept").respond(200, json={"decision": "allow"})
    sdk = AgentOpsSDK(api_key="test-key")
    with pytest.raises(AgentOpsUnavailableError):
        await sdk.intercept(agent_id="agent-1", tool_name="rm", tool_input={})
    await sdk.close()


def test_invalid_fail_mode_defaults_to_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTOPS_FAIL_MODE", "yolo")
    sdk = AgentOpsSDK(api_key="test-key")
    assert sdk.fail_mode == "closed"
