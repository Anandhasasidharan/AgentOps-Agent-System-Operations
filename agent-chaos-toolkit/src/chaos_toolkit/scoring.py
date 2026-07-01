"""Scoring Engine — computes resilience scores and generates recommendations."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.models import Experiment, ExperimentReport
from chaos_toolkit.schemas import ResilienceScoreSummary


async def compute_resilience_score(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    experiment_ids: list[uuid.UUID] | None = None,
) -> ResilienceScoreSummary:
    stmt = select(Experiment).where(Experiment.tenant_id == tenant_id)
    if experiment_ids:
        stmt = stmt.where(Experiment.id.in_(experiment_ids))

    result = await session.execute(stmt)
    experiments = list(result.scalars().all())

    if not experiments:
        return ResilienceScoreSummary(
            total_experiments=0,
            passed=0,
            failed=0,
            pass_rate=0.0,
            avg_resilience_score=0.0,
            worst_performing_target=None,
            recommendations=[],
        )

    total = len(experiments)
    scores = [e.resilience_score or 0.0 for e in experiments]
    passed_count = sum(1 for s in scores if s >= 0.7)
    failed_count = total - passed_count

    avg_score = sum(scores) / total if total > 0 else 0.0

    by_target: dict[str, list[float]] = defaultdict(list)
    for exp in experiments:
        by_target[exp.target_type].append(exp.resilience_score or 0.0)

    worst_target = None
    worst_avg = 1.0
    for target, target_scores in by_target.items():
        target_avg = sum(target_scores) / len(target_scores)
        if target_avg < worst_avg:
            worst_avg = target_avg
            worst_target = target

    recommendations = _generate_recommendations(by_target)

    return ResilienceScoreSummary(
        total_experiments=total,
        passed=passed_count,
        failed=failed_count,
        pass_rate=passed_count / total if total > 0 else 0.0,
        avg_resilience_score=avg_score,
        worst_performing_target=worst_target,
        recommendations=recommendations,
    )


def _generate_recommendations(
    by_target: dict[str, list[float]],
) -> list[str]:
    recs: list[str] = []
    for target, scores in sorted(by_target.items()):
        avg = sum(scores) / len(scores) if scores else 0.0
        if avg < 0.5:
            recs.append(
                f"Critical: {target} target has very low resilience ({avg:.0%}). "
                f"Add retry logic, fallback mechanisms, and timeout handling."
            )
        elif avg < 0.7:
            recs.append(
                f"Warning: {target} target needs improvement ({avg:.0%}). "
                f"Consider adding circuit breakers or graceful degradation."
            )
        elif avg < 0.9:
            recs.append(
                f"Info: {target} target is adequate ({avg:.0%}). "
                f"Review edge cases for further hardening."
            )
    if not recs:
        recs.append("All targets have excellent resilience scores. Continue monitoring.")
    return recs


async def create_report(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    description: str | None = None,
    experiment_ids: list[uuid.UUID] | None = None,
    ci_run_id: str | None = None,
    ci_provider: str | None = None,
) -> ExperimentReport:
    summary = await compute_resilience_score(session, tenant_id, experiment_ids)

    report = ExperimentReport(
        tenant_id=tenant_id,
        name=name,
        description=description,
        summary=summary.model_dump(),
        overall_score=summary.avg_resilience_score,
        ci_run_id=ci_run_id,
        ci_provider=ci_provider,
    )
    session.add(report)
    await session.flush()
    return report
