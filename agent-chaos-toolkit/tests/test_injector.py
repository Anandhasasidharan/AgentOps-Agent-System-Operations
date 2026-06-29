"""Tests for the Chaos Injector."""

import uuid

import pytest

from chaos_toolkit.injector import evaluate_experiment_result, run_experiment
from chaos_toolkit.models import Experiment


@pytest.mark.asyncio
async def test_run_experiment_llm_timeout(session, sample_scenario):
    experiment = await run_experiment(
        session, sample_scenario.tenant_id, sample_scenario.id,
        "test-agent-1",
    )
    assert experiment.status == "completed"
    assert experiment.injection_successful
    assert experiment.target_type == "llm"
    assert experiment.failure_mode == "timeout"


@pytest.mark.asyncio
async def test_run_experiment_tool_crash(session, sample_tool_scenario):
    experiment = await run_experiment(
        session, sample_tool_scenario.tenant_id, sample_tool_scenario.id,
        "test-agent-2",
    )
    assert experiment.status == "completed"
    assert experiment.injection_successful
    assert experiment.target_type == "tool"
    assert experiment.failure_mode == "crash"
    assert experiment.injection_details["status_code"] == 500


@pytest.mark.asyncio
async def test_run_experiment_with_overrides(session, sample_scenario):
    experiment = await run_experiment(
        session, sample_scenario.tenant_id, sample_scenario.id,
        "test-agent-3",
        target_override="tool",
        failure_mode_override="wrong_data",
    )
    assert experiment.target_type == "tool"
    assert experiment.failure_mode == "wrong_data"


@pytest.mark.asyncio
async def test_run_experiment_creates_fault_log(session, sample_scenario):
    experiment = await run_experiment(
        session, sample_scenario.tenant_id, sample_scenario.id,
        "test-agent-4",
    )

    from chaos_toolkit.models import FaultLog
    from sqlalchemy import select
    result = await session.execute(
        select(FaultLog).where(FaultLog.experiment_id == experiment.id)
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].target_type == "llm"
    assert logs[0].failure_mode == "timeout"


@pytest.mark.asyncio
async def test_run_experiment_invalid_scenario(session):
    with pytest.raises(ValueError, match="not found"):
        await run_experiment(session, uuid.uuid4(), uuid.uuid4(), "test-agent")


@pytest.mark.asyncio
async def test_evaluate_experiment_result_success(session):
    exp = Experiment(
        tenant_id=uuid.uuid4(),
        scenario_id=uuid.uuid4(),
        scenario_name="test",
        target_type="llm",
        failure_mode="timeout",
        agent_id="test-agent",
        status="completed",
        injection_successful=True,
        agent_survived=True,
        agent_behavior="graceful_degradation",
    )
    survived, score = await evaluate_experiment_result(exp, "graceful_degradation")
    assert survived
    assert score == 1.0


@pytest.mark.asyncio
async def test_evaluate_experiment_result_failure(session):
    exp = Experiment(
        tenant_id=uuid.uuid4(),
        scenario_id=uuid.uuid4(),
        scenario_name="test",
        target_type="tool",
        failure_mode="crash",
        agent_id="test-agent",
        status="completed",
        injection_successful=True,
        agent_survived=False,
        agent_error="Agent crashed",
    )
    survived, score = await evaluate_experiment_result(exp, "error_handled")
    assert not survived
    assert score == 0.2  # injection succeeded, agent errored -> partial score


@pytest.mark.asyncio
async def test_evaluate_injection_failed(session):
    exp = Experiment(
        tenant_id=uuid.uuid4(),
        scenario_id=uuid.uuid4(),
        scenario_name="test",
        target_type="llm",
        failure_mode="timeout",
        agent_id="test-agent",
        status="failed",
        injection_successful=False,
    )
    survived, score = await evaluate_experiment_result(exp, "graceful_degradation")
    assert not survived
    assert score == 0.0
