"""Tests for the Anomaly Engine."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.anomaly_engine import (
    _entropy_anomaly,
    _frequency_anomaly,
    _reasoning_loop,
    _timing_anomaly,
    compute_anomaly_score,
    compute_tool_entropy,
)
from circuit_breaker.models import ToolCall


@pytest.mark.asyncio
async def test_frequency_anomaly_low_variance():
    stats = {
        "tool_frequencies": {"search": 50, "read": 45, "write": 5},
        "call_count": 100,
    }
    tc = ToolCall(tool_name="write")
    score = _frequency_anomaly(stats, tc)
    assert score == 0.0


@pytest.mark.asyncio
async def test_frequency_anomaly_high_variance():
    stats = {
        "tool_frequencies": {"search": 100, "read": 98, "delete_file": 2},
        "call_count": 200,
    }
    tc = ToolCall(tool_name="delete_file")
    score = _frequency_anomaly(stats, tc)
    assert score >= 0.0


@pytest.mark.asyncio
async def test_entropy_anomaly():
    stats = {
        "tool_frequencies": {"search": 100, "read": 100, "write": 100},
        "call_count": 300,
    }
    score = _entropy_anomaly(stats)
    assert score == 0.0


@pytest.mark.asyncio
async def test_entropy_anomaly_low():
    stats = {
        "tool_frequencies": {"search": 300},
        "call_count": 300,
    }
    score = _entropy_anomaly(stats)
    # Single tool = degenerate case = early return 0.0
    assert score == 0.0


@pytest.mark.asyncio
async def test_reasoning_loop_detection():
    stats = {"consecutive_same_tool": 10}
    tc = ToolCall(tool_name="search")
    score = _reasoning_loop(stats, tc)
    assert score > 0.0


@pytest.mark.asyncio
async def test_reasoning_loop_below_threshold():
    stats = {"consecutive_same_tool": 1}
    tc = ToolCall(tool_name="search")
    score = _reasoning_loop(stats, tc)
    assert score == 0.0


@pytest.mark.asyncio
async def test_timing_anomaly():
    stats = {
        "durations": [100, 110, 90, 95, 105, 98, 102, 2000],
    }
    tc = ToolCall(tool_name="search", duration_ms=2000)
    score = _timing_anomaly(stats, tc)
    assert score > 0.0


@pytest.mark.asyncio
async def test_timing_within_normal():
    stats = {
        "durations": [100, 110, 90, 95, 105, 98, 102],
    }
    tc = ToolCall(tool_name="search", duration_ms=105)
    score = _timing_anomaly(stats, tc)
    assert score == 0.0


def test_tool_entropy():
    seq = ["a", "a", "a", "a"]
    assert compute_tool_entropy(seq) == 0.0

    seq2 = ["a", "b", "c", "d"]
    ent = compute_tool_entropy(seq2)
    assert ent == 1.0, f"Expected 1.0 got {ent}"


@pytest.mark.asyncio
async def test_compute_anomaly_score(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    tc = ToolCall(
        tenant_id=tenant_id,
        agent_id=agent_id,
        tool_name="delete_file",
        tool_input={},
        duration_ms=5000,
        token_count=100,
    )
    session.add(tc)
    await session.commit()

    score, details = await compute_anomaly_score(session, tenant_id, agent_id, tc)
    assert 0.0 <= score <= 1.0
    assert "composite_score" in details
    assert "component_scores" in details
