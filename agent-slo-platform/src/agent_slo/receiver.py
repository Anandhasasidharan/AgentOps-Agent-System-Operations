"""OTel trace receiver and metric derivation."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.extractor import extract_sli_metrics, parse_otlp_spans
from agent_slo.models import Agent, Metric, OtelSpan, ServiceLevelIndicator


async def ingest_traces(
    session: AsyncSession,
    payload: dict[str, Any],
    tenant_id: uuid.UUID,
) -> dict[str, int]:
    """Persist spans and derive metrics. Returns counts."""
    spans = parse_otlp_spans(payload, tenant_id)
    if not spans:
        return {"spans": 0, "metrics": 0}

    # Resolve agent by name if not UUID and ensure exists
    resolved_spans: list[OtelSpan] = []
    for span in spans:
        agent_id = span.agent_id
        if not agent_id:
            agent_name = span.attributes.get("agentops.agent.id")
            env = span.attributes.get("agentops.environment", "production")
            if agent_name:
                agent_id = await _resolve_agent(session, tenant_id, env, str(agent_name))
                span.agent_id = agent_id
        resolved_spans.append(span)

    session.add_all(resolved_spans)
    await session.flush()

    metrics_inserted = await _derive_metrics(session, resolved_spans, tenant_id)
    return {"spans": len(resolved_spans), "metrics": metrics_inserted}


async def _resolve_agent(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    environment: str,
    name: str,
) -> uuid.UUID | None:
    stmt = select(Agent).where(
        Agent.tenant_id == tenant_id,
        Agent.environment == environment,
        Agent.name == name,
    )
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent:
        return agent.id

    # Auto-create agent on first sight
    agent = Agent(
        tenant_id=tenant_id,
        environment=environment,
        name=name,
        framework=None,
        model_provider=None,
    )
    session.add(agent)
    await session.flush()
    return agent.id


async def _derive_metrics(
    session: AsyncSession,
    spans: list[OtelSpan],
    tenant_id: uuid.UUID,
) -> int:
    """Create Metric rows from spans for known SLIs."""
    # Map SLI name -> SLI object
    stmt = select(ServiceLevelIndicator).where(ServiceLevelIndicator.tenant_id == tenant_id)
    result = await session.execute(stmt)
    slis = {sli.name: sli for sli in result.scalars().all()}

    metrics: list[Metric] = []
    for span in spans:
        metrics_map = extract_sli_metrics(span)
        window_start = span.start_time
        window_end = span.end_time

        # success / eval_total -> task_success_rate
        if "task_success" in metrics_map and "eval_total" in metrics_map:
            total = metrics_map.get("eval_total", 1)
            if total > 0 and "task_success_rate" in slis:
                metrics.append(
                    Metric(
                        tenant_id=tenant_id,
                        agent_id=span.agent_id,
                        sli_id=slis["task_success_rate"].id,
                        timestamp=span.end_time,
                        value=metrics_map["task_success"] / total,
                        count=int(total),
                        window_start=window_start,
                        window_end=window_end,
                    )
                )

        # hallucination / eval_total -> hallucination_rate
        if "hallucination" in metrics_map and "eval_total" in metrics_map:
            total = metrics_map.get("eval_total", 1)
            if total > 0 and "hallucination_rate" in slis:
                metrics.append(
                    Metric(
                        tenant_id=tenant_id,
                        agent_id=span.agent_id,
                        sli_id=slis["hallucination_rate"].id,
                        timestamp=span.end_time,
                        value=metrics_map["hallucination"] / total,
                        count=int(total),
                        window_start=window_start,
                        window_end=window_end,
                    )
                )

        # tool_success / tool_calls -> tool_accuracy
        if "tool_success" in metrics_map and "tool_calls" in metrics_map:
            total = metrics_map.get("tool_calls", 1)
            if total > 0 and "tool_accuracy" in slis:
                metrics.append(
                    Metric(
                        tenant_id=tenant_id,
                        agent_id=span.agent_id,
                        sli_id=slis["tool_accuracy"].id,
                        timestamp=span.end_time,
                        value=metrics_map["tool_success"] / total,
                        count=int(total),
                        window_start=window_start,
                        window_end=window_end,
                    )
                )

        # latency_ms -> latency_p99 (per-span metric; p99 computed at query time)
        if "latency_ms" in metrics_map and "latency_p99" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["latency_p99"].id,
                    timestamp=span.end_time,
                    value=metrics_map["latency_ms"],
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )

        # token_usage
        if (
            "input_tokens" in metrics_map or "output_tokens" in metrics_map
        ) and "token_usage" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["token_usage"].id,
                    timestamp=span.end_time,
                    value=metrics_map.get("input_tokens", 0) + metrics_map.get("output_tokens", 0),
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )

        # total_tokens (GenAI semconv native)
        if "total_tokens" in metrics_map and "token_usage" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["token_usage"].id,
                    timestamp=span.end_time,
                    value=metrics_map["total_tokens"],
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )

        # prompt_tokens / completion_tokens (GenAI semconv)
        if "prompt_tokens" in metrics_map and "prompt_tokens" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["prompt_tokens"].id,
                    timestamp=span.end_time,
                    value=metrics_map["prompt_tokens"],
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
        if "completion_tokens" in metrics_map and "completion_tokens" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["completion_tokens"].id,
                    timestamp=span.end_time,
                    value=metrics_map["completion_tokens"],
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )

        # trust_score (from VeriAlign verification)
        if "trust_score" in metrics_map and "trust_score" in slis:
            metrics.append(
                Metric(
                    tenant_id=tenant_id,
                    agent_id=span.agent_id,
                    sli_id=slis["trust_score"].id,
                    timestamp=span.end_time,
                    value=metrics_map["trust_score"],
                    count=1,
                    window_start=window_start,
                    window_end=window_end,
                )
            )

    session.add_all(metrics)
    await session.flush()
    return len(metrics)
