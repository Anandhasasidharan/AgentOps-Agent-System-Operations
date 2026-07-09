"""FastAPI application."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from agentops_core.auth import generate_api_key, make_get_tenant
from agentops_core.base import Tenant
from agentops_core.rate_limiter import add_rate_limiter
from agentops_events import (
    TOPIC_SLO_ALERT,
    TOPIC_SLO_BREACH,
    create_nats_client,
    make_event,
    publish_event,
)
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.alerts import evaluate_alerts, resolve_alerts
from agent_slo.compliance import generate_owasp_report
from agent_slo.config import Settings
from agent_slo.db import engine, get_db
from agent_slo.engine import evaluate_all_slos
from agent_slo.metrics import (
    add_metrics_route,
    events_dropped_total,
    otel_spans_ingested_total,
    sli_requests_total,
    slo_alerts_total,
    slo_breaching,
    slo_budget_remaining,
    slo_burn_rate,
    slo_current_value,
    slo_target,
)
from agent_slo.models import (
    Agent,
    Alert,
    Base,
    ServiceLevelIndicator,
    ServiceLevelObjective,
)
from agent_slo.receiver import ingest_traces
from agent_slo.schemas import (
    AgentCreate,
    AgentOut,
    AlertOut,
    ComplianceReport,
    KeyRotateResponse,
    SLICreate,
    SLIOut,
    SLOCreate,
    SLOut,
    StatusEntry,
    TenantCreate,
    TenantOut,
)

settings = Settings()

nats_nc = None


async def _pub(event: Any):
    try:
        await publish_event(nats_nc, event)
    except Exception:
        events_dropped_total.labels(reason="publish_failed", service="slo-platform").inc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nats_nc
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    nats_nc = await create_nats_client(settings.nats_url)
    yield
    if nats_nc:
        await nats_nc.close()
    await engine.dispose()


app = FastAPI(title="Agent SLO Platform", version="0.1.0", lifespan=lifespan)

add_metrics_route(app)
add_rate_limiter(app, settings.rate_limit_rpm)
get_tenant = make_get_tenant(get_db)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/tenants", response_model=TenantOut, status_code=201)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_db),
) -> Tenant:
    raw_key, key_hash = generate_api_key(data.slug)
    tenant = Tenant(slug=data.slug, name=data.name, api_key_hash=key_hash)
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return TenantOut(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        api_key=raw_key,
        created_at=tenant.created_at,
    )


@app.post("/api/v1/keys/rotate", response_model=KeyRotateResponse)
async def rotate_key(
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict:
    new_raw, new_hash = generate_api_key(tenant.slug)
    tenant.api_key_hash = new_hash
    session.add(tenant)
    await session.commit()
    return {"api_key": new_raw, "tenant_id": tenant.id}


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
    sli_requests_total.labels(sli_name=sli.name, metric_type=sli.metric_type).inc()
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

        slo_name = s["slo_name"]
        slo_current_value.labels(slo_name=slo_name).set(s["current_value"])
        slo_target.labels(slo_name=slo_name).set(s["target"])
        slo_burn_rate.labels(slo_name=slo_name).set(s["burn_rate"])
        slo_budget_remaining.labels(slo_name=slo_name).set(s["budget_remaining"])
        slo_breaching.labels(slo_name=slo_name).set(1 if s["is_breaching"] else 0)
        if severity:
            slo_alerts_total.labels(severity=severity, slo_name=slo_name).inc()
            await _pub(
                make_event(
                    "slo-platform",
                    TOPIC_SLO_ALERT.format(severity=severity),
                    tenant.id,
                    {
                        "slo_id": str(s["slo_id"]),
                        "slo_name": slo_name,
                        "burn_rate": s["burn_rate"],
                        "severity": severity,
                        "budget_remaining": s["budget_remaining"],
                        "is_breaching": s["is_breaching"],
                    },
                )
            )
        if s.get("is_breaching"):
            await _pub(
                make_event(
                    "slo-platform",
                    TOPIC_SLO_BREACH.format(window=s["window"]),
                    tenant.id,
                    {
                        "slo_id": str(s["slo_id"]),
                        "slo_name": slo_name,
                        "sli_name": s["sli_name"],
                        "target": s["target"],
                        "current_value": s["current_value"],
                        "budget_remaining": s["budget_remaining"],
                        "burn_rate": s["burn_rate"],
                    },
                )
            )

        entries.append(
            StatusEntry(
                slo_id=s["slo_id"],
                slo_name=slo_name,
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
            )
        )
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
    from agentops_core.base import now_utc as model_now_utc

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
    return JSONResponse(
        {
            "tenant": str(tenant.id),
            "standard": "EU AI Act",
            "note": "Evidence generator scaffold; Article 12 logging enabled via otel_spans table.",
            "controls": ["Art. 12 traceability", "Art. 14 human oversight via alert resolve"],
        }
    )


@app.post(settings.otel_receiver_path)
async def receive_otlp(
    request: Request,
    tenant: Tenant = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    payload = await request.json()
    counts = await ingest_traces(session, payload, tenant.id)
    await session.commit()
    otel_spans_ingested_total.inc(counts.get("spans_ingested", 1))
    return counts
