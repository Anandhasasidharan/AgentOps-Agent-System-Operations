"""FastAPI application for Agent Chaos Toolkit."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.config import Settings
from chaos_toolkit.db import AsyncSessionLocal, engine, get_db
from chaos_toolkit.injector import evaluate_experiment_result, run_batch, run_experiment
from chaos_toolkit.models import Base, Experiment, ExperimentReport, Scenario
from chaos_toolkit.reporters.ci import generate_github_actions_summary, generate_junit_xml
from chaos_toolkit.scenarios import seed_builtin_scenarios
from chaos_toolkit.schemas import (
    ExperimentBatchRequest,
    ExperimentOut,
    ExperimentReportOut,
    ExperimentRunRequest,
    ResilienceScoreSummary,
    ScenarioCreate,
    ScenarioOut,
)
from chaos_toolkit.scoring import compute_resilience_score, create_report

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Agent Chaos Toolkit", version="0.1.0", lifespan=lifespan)

API_KEY_HEADER = "X-API-Key"


async def get_tenant(
    x_api_key: str = Header(..., alias=API_KEY_HEADER),
) -> uuid.UUID:
    try:
        return uuid.UUID(x_api_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key (must be tenant UUID)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── Scenarios ────────────────────────────────────────────────────────────────


@app.post("/api/v1/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(
    data: ScenarioCreate,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Scenario:
    scenario = Scenario(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        target_type=data.target_type,
        failure_mode=data.failure_mode,
        config=data.config,
        expected_behavior=data.expected_behavior,
        agent_should_survive=data.agent_should_survive,
        enabled=data.enabled,
    )
    session.add(scenario)
    await session.commit()
    await session.refresh(scenario)
    return scenario


@app.get("/api/v1/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(
    tenant_id: uuid.UUID = Depends(get_tenant),
    target_type: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> list[Scenario]:
    stmt = select(Scenario).where(Scenario.tenant_id == tenant_id)
    if target_type:
        stmt = stmt.where(Scenario.target_type == target_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Scenario:
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.tenant_id == tenant_id)
    result = await session.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@app.post("/api/v1/scenarios/seed", response_model=list[ScenarioOut])
async def seed_scenarios(
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Scenario]:
    scenarios = await seed_builtin_scenarios(session, tenant_id)
    await session.commit()
    return scenarios


# ─── Experiments ──────────────────────────────────────────────────────────────


@app.post("/api/v1/experiments", response_model=ExperimentOut, status_code=201)
async def create_experiment(
    data: ExperimentRunRequest,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Experiment:
    experiment = await run_experiment(
        session, tenant_id, data.scenario_id, data.agent_id,
        data.target_override, data.failure_mode_override, data.config_override,
    )
    # Get scenario to evaluate result
    stmt = select(Scenario).where(Scenario.id == data.scenario_id)
    result = await session.execute(stmt)
    scenario = result.scalar_one()
    await evaluate_experiment_result(experiment, scenario.expected_behavior)
    await session.commit()
    return experiment


@app.post("/api/v1/experiments/batch", response_model=list[ExperimentOut])
async def batch_experiments(
    data: ExperimentBatchRequest,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Experiment]:
    experiments = await run_batch(
        session, tenant_id, data.agent_id,
        data.scenarios if data.scenarios else None,
        data.run_all_enabled,
    )
    await session.commit()
    return experiments


@app.get("/api/v1/experiments", response_model=list[ExperimentOut])
async def list_experiments(
    tenant_id: uuid.UUID = Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[Experiment]:
    stmt = select(Experiment).where(Experiment.tenant_id == tenant_id)
    if agent_id:
        stmt = stmt.where(Experiment.agent_id == agent_id)
    stmt = stmt.order_by(Experiment.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(
    experiment_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Experiment:
    stmt = select(Experiment).where(Experiment.id == experiment_id, Experiment.tenant_id == tenant_id)
    result = await session.execute(stmt)
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


# ─── Scoring ──────────────────────────────────────────────────────────────────


@app.get("/api/v1/resilience-score", response_model=ResilienceScoreSummary)
async def get_resilience_score(
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ResilienceScoreSummary:
    return await compute_resilience_score(session, tenant_id)


# ─── Reports ──────────────────────────────────────────────────────────────────


@app.post("/api/v1/reports", response_model=ExperimentReportOut, status_code=201)
async def create_report(
    name: str = Query(...),
    description: str | None = Query(None),
    ci_run_id: str | None = Query(None),
    ci_provider: str | None = Query(None),
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ExperimentReport:
    report = await create_report(
        session, tenant_id, name, description,
        ci_run_id=ci_run_id, ci_provider=ci_provider,
    )
    await session.commit()
    await session.refresh(report)
    return report


@app.get("/api/v1/reports", response_model=list[ExperimentReportOut])
async def list_reports(
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[ExperimentReport]:
    stmt = select(ExperimentReport).where(
        ExperimentReport.tenant_id == tenant_id
    ).order_by(ExperimentReport.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/reports/{report_id}/junit")
async def get_junit_report(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> str:
    stmt = select(ExperimentReport).where(
        ExperimentReport.id == report_id,
        ExperimentReport.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    stmt_exp = select(Experiment).where(Experiment.tenant_id == tenant_id)
    exps = (await session.execute(stmt_exp)).scalars().all()
    return generate_junit_xml(list(exps))


@app.get("/api/v1/reports/{report_id}/github-summary")
async def get_github_summary(
    report_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> str:
    stmt = select(ExperimentReport).where(
        ExperimentReport.id == report_id,
        ExperimentReport.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    stmt_exp = select(Experiment).where(Experiment.tenant_id == tenant_id)
    exps = (await session.execute(stmt_exp)).scalars().all()
    return "\n".join(generate_github_actions_summary(list(exps)))
