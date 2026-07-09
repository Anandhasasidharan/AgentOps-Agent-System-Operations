"""FastAPI application for Agent Chaos Toolkit."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from agentops_core.auth import make_get_tenant
from agentops_core.rate_limiter import add_rate_limiter
from agentops_events import TOPIC_CHAOS_EXPERIMENT, create_nats_client, make_event, publish_event
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.config import Settings
from chaos_toolkit.db import engine, get_db
from chaos_toolkit.injector import evaluate_experiment_result, run_batch, run_experiment
from chaos_toolkit.metrics import (
    add_metrics_route,
    events_dropped_total,
    experiments_total,
    resilience_score,
    scenarios_total,
)
from chaos_toolkit.models import Base, Experiment, ExperimentReport, Scenario
from chaos_toolkit.reporters.ci import generate_github_actions_summary, generate_junit_xml
from chaos_toolkit.scenario_proposer import propose_scenarios, refine_proposals
from chaos_toolkit.scenarios import seed_builtin_scenarios
from chaos_toolkit.schemas import (
    ExperimentBatchRequest,
    ExperimentOut,
    ExperimentReportOut,
    ExperimentRunRequest,
    ProposeRequest,
    ProposeResponse,
    ProposedScenario,
    ResilienceScoreSummary,
    ScenarioCreate,
    ScenarioOut,
)
from chaos_toolkit.scoring import compute_resilience_score
from chaos_toolkit.scoring import create_report as _create_report

logger = logging.getLogger(__name__)

settings = Settings()

nats_nc = None
sub_tasks: list[asyncio.Task] = []


async def _pub(event: Any):
    try:
        await publish_event(nats_nc, event)
    except Exception:
        events_dropped_total.labels(reason="publish_failed", service="chaos-toolkit").inc()


async def handle_cb_incident(msg):
    try:
        data = json.loads(msg.data.decode())
        payload = data.get("payload", {})
        agent_id = payload.get("agent_id") or data.get("agent_id")
        tenant_id = data.get("tenant_id")
        if not agent_id or not tenant_id:
            return
        from chaos_toolkit.db import get_db
        async with get_db() as session:
            stmt = select(Scenario).where(
                Scenario.tenant_id == uuid.UUID(tenant_id),
                Scenario.enabled,
            )
            result = await session.execute(stmt)
            scenarios = list(result.scalars().all())
            for sc in scenarios[:3]:
                exp = await run_experiment(
                    session, uuid.UUID(tenant_id), sc.id, agent_id,
                    tenant_slug=None,
                )
                await evaluate_experiment_result(exp, sc.expected_behavior)
            await session.commit()
            logger.info(
                "ran %d experiments after CB incident for %s",
                min(len(scenarios), 3), agent_id,
            )
    except Exception:
        logger.exception("error handling CB incident in Chaos")


async def subscribe_cross_service():
    if not nats_nc:
        return
    await nats_nc.subscribe("agentops.cb.incident.*", cb=handle_cb_incident)
    logger.info("Chaos subscribed to agentops.cb.incident.*")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nats_nc
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    nats_nc = await create_nats_client(settings.nats_url)
    sub_tasks.append(asyncio.ensure_future(subscribe_cross_service()))
    yield
    for t in sub_tasks:
        t.cancel()
    if nats_nc:
        await nats_nc.close()
    await engine.dispose()


app = FastAPI(title="Agent Chaos Toolkit", version="0.1.0", lifespan=lifespan)

add_metrics_route(app)
add_rate_limiter(app, settings.rate_limit_rpm)
get_tenant = make_get_tenant(get_db)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── Scenarios ────────────────────────────────────────────────────────────────


@app.post("/api/v1/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(
    data: ScenarioCreate,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Scenario:
    scenario = Scenario(
        tenant_id=tenant.id,
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
    tenant=Depends(get_tenant),
    target_type: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> list[Scenario]:
    stmt = select(Scenario).where(Scenario.tenant_id == tenant.id)
    if target_type:
        stmt = stmt.where(Scenario.target_type == target_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Scenario:
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.tenant_id == tenant.id)
    result = await session.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@app.post("/api/v1/scenarios/seed", response_model=list[ScenarioOut])
async def seed_scenarios(
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Scenario]:
    scenarios = await seed_builtin_scenarios(session, tenant.id)
    await session.commit()
    for s in scenarios:
        scenarios_total.labels(target_type=s.target_type, tenant_id=str(tenant.id)).inc()
    return scenarios


# ─── Propose & Refine ──────────────────────────────────────────────────────────


@app.post("/api/v1/scenarios/propose", response_model=ProposeResponse)
async def propose(
    data: ProposeRequest,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ProposeResponse:
    proposals = await propose_scenarios(session, tenant.id, data.agent_id, data.model)
    return ProposeResponse(
        proposals=[ProposedScenario(**p) for p in proposals]
    )


@app.post("/api/v1/scenarios/refine", response_model=ProposeResponse)
async def refine(
    data: ProposeRequest,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ProposeResponse:
    proposals = await refine_proposals(session, tenant.id, data.agent_id or "", data.model)
    return ProposeResponse(
        proposals=[ProposedScenario(**p) for p in proposals]
    )


# ─── Experiments ──────────────────────────────────────────────────────────────


@app.post("/api/v1/experiments", response_model=ExperimentOut, status_code=201)
async def create_experiment(
    data: ExperimentRunRequest,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Experiment:
    experiment = await run_experiment(
        session,
        tenant.id,
        data.scenario_id,
        data.agent_id,
        data.target_override,
        data.failure_mode_override,
        data.config_override,
        tenant_slug=tenant.slug,
    )
    # Get scenario to evaluate result
    stmt = select(Scenario).where(Scenario.id == data.scenario_id)
    result = await session.execute(stmt)
    scenario = result.scalar_one()
    await evaluate_experiment_result(experiment, scenario.expected_behavior)
    await session.commit()
    status = experiment.status or "unknown"
    experiments_total.labels(status=status, target_type=scenario.target_type).inc()
    await _pub(
        make_event(
            "chaos-toolkit",
            TOPIC_CHAOS_EXPERIMENT.format(
                status="completed" if status == "completed" else "failed"
            ),
            tenant.id,
            {
                "agent_id": data.agent_id,
                "experiment_id": str(experiment.id),
                "scenario_id": str(data.scenario_id),
                "scenario_name": experiment.scenario_name,
                "target_type": scenario.target_type,
                "failure_mode": experiment.failure_mode,
                "status": status,
                "resilience_score": experiment.resilience_score,
                "agent_survived": experiment.agent_survived,
            },
            agent_id=data.agent_id,
        )
    )
    return experiment


@app.post("/api/v1/experiments/batch", response_model=list[ExperimentOut])
async def batch_experiments(
    data: ExperimentBatchRequest,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Experiment]:
    experiments = await run_batch(
        session,
        tenant.id,
        data.agent_id,
        data.scenarios if data.scenarios else None,
        data.run_all_enabled,
        tenant_slug=tenant.slug,
    )
    await session.commit()
    return experiments


@app.get("/api/v1/experiments", response_model=list[ExperimentOut])
async def list_experiments(
    tenant=Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[Experiment]:
    stmt = select(Experiment).where(Experiment.tenant_id == tenant.id)
    if agent_id:
        stmt = stmt.where(Experiment.agent_id == agent_id)
    stmt = stmt.order_by(Experiment.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(
    experiment_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Experiment:
    stmt = select(Experiment).where(
        Experiment.id == experiment_id, Experiment.tenant_id == tenant.id
    )
    result = await session.execute(stmt)
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


# ─── Scoring ──────────────────────────────────────────────────────────────────


@app.get("/api/v1/resilience-score", response_model=ResilienceScoreSummary)
async def get_resilience_score(
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ResilienceScoreSummary:
    score = await compute_resilience_score(session, tenant.id)
    resilience_score.labels(tenant_id=str(tenant.id)).set(score.avg_resilience_score)
    return score


# ─── Reports ──────────────────────────────────────────────────────────────────


@app.post("/api/v1/reports", response_model=ExperimentReportOut, status_code=201)
async def create_report(
    name: str = Query(...),
    description: str | None = Query(None),
    ci_run_id: str | None = Query(None),
    ci_provider: str | None = Query(None),
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ExperimentReport:
    report = await _create_report(
        session,
        tenant.id,
        name,
        description,
        ci_run_id=ci_run_id,
        ci_provider=ci_provider,
    )
    await session.commit()
    await session.refresh(report)
    return report


@app.get("/api/v1/reports", response_model=list[ExperimentReportOut])
async def list_reports(
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[ExperimentReport]:
    stmt = (
        select(ExperimentReport)
        .where(ExperimentReport.tenant_id == tenant.id)
        .order_by(ExperimentReport.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/reports/{report_id}/junit")
async def get_junit_report(
    report_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> str:
    stmt = select(ExperimentReport).where(
        ExperimentReport.id == report_id,
        ExperimentReport.tenant_id == tenant.id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    stmt_exp = select(Experiment).where(Experiment.tenant_id == tenant.id)
    exps = (await session.execute(stmt_exp)).scalars().all()
    return generate_junit_xml(list(exps))


@app.get("/api/v1/reports/{report_id}/github-summary")
async def get_github_summary(
    report_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> str:
    stmt = select(ExperimentReport).where(
        ExperimentReport.id == report_id,
        ExperimentReport.tenant_id == tenant.id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    stmt_exp = select(Experiment).where(Experiment.tenant_id == tenant.id)
    exps = (await session.execute(stmt_exp)).scalars().all()
    return "\n".join(generate_github_actions_summary(list(exps)))
