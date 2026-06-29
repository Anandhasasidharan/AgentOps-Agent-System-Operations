"""Chaos Injector — main orchestrator for fault injection experiments.

Routes to the correct target injector based on scenario definition,
logs results, and returns experiment outcome.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.models import Experiment, FaultLog, Scenario
from chaos_toolkit.targets.llm import inject_llm_fault
from chaos_toolkit.targets.mcp import inject_mcp_fault
from chaos_toolkit.targets.rag import inject_rag_fault
from chaos_toolkit.targets.tools import inject_tool_fault


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


TARGET_INJECTORS = {
    "llm": inject_llm_fault,
    "tool": inject_tool_fault,
    "rag": inject_rag_fault,
    "mcp": inject_mcp_fault,
}


async def run_experiment(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    scenario_id: uuid.UUID,
    agent_id: str,
    target_override: str | None = None,
    failure_mode_override: str | None = None,
    config_override: dict[str, Any] | None = None,
) -> Experiment:
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.tenant_id == tenant_id)
    result = await session.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    target_type = target_override or scenario.target_type
    failure_mode = failure_mode_override or scenario.failure_mode
    config = dict(scenario.config or {})
    if config_override:
        config.update(config_override)
    config["failure_mode"] = failure_mode

    injector = TARGET_INJECTORS.get(target_type)
    if not injector:
        raise ValueError(f"No injector for target type: {target_type}")

    experiment = Experiment(
        tenant_id=tenant_id,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        target_type=target_type,
        failure_mode=failure_mode,
        agent_id=agent_id,
        status="running",
        created_at=now_utc(),
    )
    session.add(experiment)
    await session.flush()

    inject_start = time.monotonic()
    try:
        fault_result = await injector(config)
        injection_time = (time.monotonic() - inject_start) * 1000

        experiment.injection_successful = True
        experiment.injection_details = fault_result
        experiment.status = "completed"

        fault_log = FaultLog(
            experiment_id=experiment.id,
            tenant_id=tenant_id,
            target_type=target_type,
            failure_mode=failure_mode,
            injected_fault=fault_result,
            injection_time_ms=injection_time,
            created_at=now_utc(),
        )
        session.add(fault_log)

    except Exception as e:
        injection_time = (time.monotonic() - inject_start) * 1000
        experiment.injection_successful = False
        experiment.injection_details = {"error": str(e)}
        experiment.status = "failed"
        experiment.agent_error = str(e)

        fault_log = FaultLog(
            experiment_id=experiment.id,
            tenant_id=tenant_id,
            target_type=target_type,
            failure_mode=failure_mode,
            injected_fault={"error": str(e)},
            injection_time_ms=injection_time,
            created_at=now_utc(),
        )
        session.add(fault_log)

    experiment.completed_at = now_utc()
    await session.flush()
    return experiment


async def evaluate_experiment_result(
    experiment: Experiment,
    expected_behavior: str,
) -> tuple[bool, float]:
    if not experiment.injection_successful:
        experiment.agent_survived = False
        experiment.resilience_score = 0.0
        return False, 0.0

    if experiment.agent_error:
        experiment.agent_survived = False
        experiment.resilience_score = 0.2
        return False, 0.2

    survived = experiment.agent_survived
    if survived is None:
        survived = True
        experiment.agent_survived = True

    behavior_ok = experiment.agent_behavior == expected_behavior if expected_behavior else True

    if survived and behavior_ok:
        score = 1.0
    elif survived:
        score = 0.7
    else:
        score = 0.0

    experiment.resilience_score = score
    return survived, score


async def run_batch(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    scenario_ids: list[uuid.UUID] | None = None,
    run_all: bool = False,
) -> list[Experiment]:
    if run_all:
        stmt = select(Scenario).where(
            Scenario.tenant_id == tenant_id,
            Scenario.enabled.is_(True),
        )
    elif scenario_ids:
        stmt = select(Scenario).where(
            Scenario.tenant_id == tenant_id,
            Scenario.id.in_(scenario_ids),
        )
    else:
        return []

    result = await session.execute(stmt)
    scenarios = list(result.scalars().all())

    experiments: list[Experiment] = []
    for scenario in scenarios:
        experiment = await run_experiment(
            session, tenant_id, scenario.id, agent_id
        )
        await evaluate_experiment_result(experiment, scenario.expected_behavior)
        experiments.append(experiment)

    await session.flush()
    return experiments
