"""FastAPI application."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.alerts import evaluate_alerts, resolve_alerts
from agent_slo.compliance import generate_owasp_report
from agent_slo.config import Settings
from agent_slo.db import AsyncSessionLocal, engine, get_db
from agent_slo.engine import evaluate_all_slos
from agent_slo.models import (
    Agent,
    Alert,
    Base,
    Metric,
    ServiceLevelIndicator,
    ServiceLevelObjective,
    Tenant,
)
from agent_slo.receiver import ingest_traces
from agent_slo.schemas import (
    AgentCreate,
    AgentOut,
    AlertOut,
    ComplianceReport,
    MetricOut,
    SLICreate,
    SLIOut,
    SLOCreate,
    SLOut,
    StatusEntry,
    TenantCreate,
    TenantOut,
)
from agent_slo.yaml_spec import parse_yaml, window_to_seconds

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Agent SLO Platform", version="0.1.0", lifespan=lifespan)


async def get_tenant(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> Tenant:
    # v1: API key maps directly to tenant slug for simplicity.
    # In production this should be a hashed lookup.
    stmt = select(Tenant).where(Tenant.slug == x_api_key)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/tenants", response_model=TenantOut, status_code=201)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_db),
) -> Tenant:
    tenant = Tenant(slug=data.slug, name=data.name)
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


@app.get("/api/v1/tenants/me", response_model=TenantOut)
async def get_me(tenant: Tenant = Depends(get_tenant)) -> Tenant:
    return tenant


@app.post("/api/v1/agents", response_model=AgentOut, status_code=201)
async def create_agent(
    data: AgentCreate,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Agent:
    agent = Agent(
        tenant_id=tenant.id,
        environment=data.environment,
        name=data.name,
        framework=data.framework,
        model_provider=data.model_provider,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@app.get("/api/v1/agents", response_model=list[AgentOut])
async def list_agents(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Agent]:
    stmt = select(Agent).where(Agent.tenant_id == tenant.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.post("/api/v1/slis", response_model=SLIOut, status_code=201)
async def create_sli(
    data: SLICreate,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ServiceLevelIndicator:
    sli = ServiceLevelIndicator(
        tenant_id=tenant.id,
        name=data.name,
        metric_type=data.metric_type,
        source=data.source,
        config=data.config,
    )
    session.add(sli)
    await session.commit()
    await session.refresh(sli)
    return sli


@app.get("/api/v1/slis", response_model=list[SLIOut])
async def list_slis(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[ServiceLevelIndicator]:
    stmt = select(ServiceLevelIndicator).where(ServiceLevelIndicator.tenant_id == tenant.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.post("/api/v1/slos", response_model=SLOut, status_code=201)
async def create_slo(
    data: SLOCreate,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> ServiceLevelObjective:
    slo = ServiceLevelObjective(
        tenant_id=tenant.id,
        sli_id=data.sli_id,
        name=data.name,
        description=data.description,
        target=data.target,
        comparator=data.comparator,
        window=data.window,
        burn_rate_alert_thresholds=data.burn_rate_alert_thresholds,
        risk_budget=data.risk_budget,
        labels=data.labels,
    )
    session.add(slo)
    await session.commit()
    await session.refresh(slo)
    return slo


@app.get("/api/v1/slos", response_model=list[SLOut])
async def list_slos(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[ServiceLevelObjective]:
    stmt = select(ServiceLevelObjective).where(ServiceLevelObjective.tenant_id == tenant.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/status", response_model=list[StatusEntry])
async def status(
    tenant: Tenant = Depends(get_tenant),
    agent_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[StatusEntry]:
    statuses = await evaluate_all_slos(session, tenant.id)
    if agent_id:
        statuses = [s for s in statuses if s.get("agent_id") == agent_id]

    entries = []
    for s in statuses:
        # fire/resolve alerts
        thresholds = s.get("alert_thresholds", [])
        # fetch SLO object for alert evaluation
        stmt_slo = select(ServiceLevelObjective).where(ServiceLevelObjective.id == s["slo_id"])
        slo_result = await session.execute(stmt_slo)
        slo_obj = slo_result.scalar_one()
        await evaluate_alerts(session, slo_obj, s["burn_rate"])
        await resolve_alerts(session, s["slo_id"], s["burn_rate"], thresholds)

        severity = None
        for t in thresholds:
            if s["burn_rate"] >= t.get("threshold", 1.0):
                severity = t.get("severity")

        entries.append(StatusEntry(
            slo_id=s["slo_id"],
            slo_name=s["slo_name"],
            sli_name=s["sli_name"],
            window=s["window"],
            target=s["target"],
            current_value=s["current_value"],
            comparator=s["comparator"],
            is_breaching=s["is_breaching"],
            budget_consumed=s["budget_consumed"],
            budget_remaining=s["budget_remaining"],
            burn_rate=s["burn_rate"],
            alert_severity=severity,
        ))
    await session.commit()
    return entries


@app.get("/api/v1/alerts", response_model=list[AlertOut])
async def list_alerts(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == tenant.id).order_by(Alert.fired_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.post("/api/v1/alerts/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: uuid.UUID,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Alert:
    stmt = select(Alert).where(Alert.id == alert_id, Alert.tenant_id == tenant.id)
    result = await session.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    from agent_slo.models import now_utc as model_now_utc
    alert.resolved_at = model_now_utc()
    await session.commit()
    await session.refresh(alert)
    return alert


@app.get("/api/v1/compliance/owasp", response_model=ComplianceReport)
async def owasp_compliance(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    report = await generate_owasp_report(session, tenant.id)
    return report


@app.get("/api/v1/compliance/eu-ai-act")
async def eu_ai_act_compliance(tenant: Tenant = Depends(get_tenant)) -> JSONResponse:
    return JSONResponse({
        "tenant": str(tenant.id),
        "standard": "EU AI Act",
        "note": "Evidence generator scaffold; Article 12 logging enabled via otel_spans table.",
        "controls": ["Art. 12 traceability", "Art. 14 human oversight via alert resolve"],
    })


@app.post(settings.otel_receiver_path)
async def receive_otlp(
    request: Request,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    payload = await request.json()
    counts = await ingest_traces(session, payload, tenant.id)
    await session.commit()
    return counts
