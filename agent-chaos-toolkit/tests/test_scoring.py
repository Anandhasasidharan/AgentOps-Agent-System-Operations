"""Tests for the Scoring Engine."""

import uuid

import pytest

from chaos_toolkit.models import Experiment, ExperimentReport
from chaos_toolkit.scoring import _generate_recommendations, compute_resilience_score, create_report


@pytest.mark.asyncio
async def test_compute_resilience_score_empty(session):
    summary = await compute_resilience_score(session, uuid.uuid4())
    assert summary.total_experiments == 0


@pytest.mark.asyncio
async def test_compute_resilience_score(session):
    tenant_id = uuid.uuid4()
    for i in range(10):
        exp = Experiment(
            tenant_id=tenant_id,
            scenario_id=uuid.uuid4(),
            scenario_name=f"test-{i}",
            target_type="llm" if i < 5 else "tool",
            failure_mode="timeout",
            agent_id="agent-1",
            status="completed",
            injection_successful=True,
            agent_survived=True,
            resilience_score=1.0 if i < 8 else 0.3,
        )
        session.add(exp)
    await session.commit()

    summary = await compute_resilience_score(session, tenant_id)
    assert summary.total_experiments == 10
    assert summary.passed == 8
    assert summary.failed == 2
    assert summary.pass_rate == 0.8
    assert summary.avg_resilience_score == pytest.approx(0.86, abs=0.01)


def test_generate_recommendations():
    by_target = {
        "llm": [1.0, 0.9, 0.95],
        "tool": [0.4, 0.3],
    }
    recs = _generate_recommendations(by_target)
    assert len(recs) >= 1
    assert any("tool" in r for r in recs)
    assert any("Critical" in r for r in recs)


@pytest.mark.asyncio
async def test_create_report(session):
    tenant_id = uuid.uuid4()
    exp = Experiment(
        tenant_id=tenant_id,
        scenario_id=uuid.uuid4(),
        scenario_name="test",
        target_type="llm",
        failure_mode="timeout",
        agent_id="agent-1",
        status="completed",
        injection_successful=True,
        agent_survived=True,
        resilience_score=1.0,
    )
    session.add(exp)
    await session.commit()

    report = await create_report(session, tenant_id, "Test Report", "A test report")
    assert report.name == "Test Report"
    assert report.overall_score == 1.0
    assert "total_experiments" in report.summary
