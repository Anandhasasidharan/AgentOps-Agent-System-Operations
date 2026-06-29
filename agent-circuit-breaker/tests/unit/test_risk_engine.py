"""Tests for the Risk Engine."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.risk_engine import (
    TOOL_RISK_WEIGHTS,
    _score_input_risk,
    score_tool_call,
)


def test_tool_risk_weights_have_high_risk_tools():
    assert "delete_file" in TOOL_RISK_WEIGHTS
    assert TOOL_RISK_WEIGHTS["delete_file"] > 0.9
    assert "execute_command" in TOOL_RISK_WEIGHTS
    assert TOOL_RISK_WEIGHTS["execute_command"] > 0.9
    assert "send_http_request" in TOOL_RISK_WEIGHTS
    assert TOOL_RISK_WEIGHTS["send_http_request"] < 0.6


def test_input_risk_clean():
    assert _score_input_risk({"path": "/tmp/file.txt"}) == 0.0


def test_input_risk_dangerous():
    score = _score_input_risk({"query": "DELETE FROM users WHERE 1=1"})
    assert score > 0.0


def test_input_risk_multiple_matches():
    score = _score_input_risk({
        "command": "rm -rf /",
        "code": "eval(malicious_code)",
    })
    assert score > 0.0


@pytest.mark.asyncio
async def test_score_tool_call_high_risk(session):
    tenant_id = uuid.uuid4()
    score, details = await score_tool_call(
        session, tenant_id, "agent-1", "delete_file", {"path": "/etc/passwd"}
    )
    assert 0.0 <= score <= 1.0
    assert score > 0.2  # delete_file has base weight 0.95 * weight 0.40 = 0.38
    assert "base_weight" in details["factor_scores"]
    assert "input_risk" in details["factor_scores"]


@pytest.mark.asyncio
async def test_score_tool_call_low_risk(session):
    tenant_id = uuid.uuid4()
    score, details = await score_tool_call(
        session, tenant_id, "agent-1", "send_http_request", {"url": "http://example.com"}
    )
    assert 0.0 <= score <= 1.0
    assert score < 0.5  # send_http_request is moderate risk
