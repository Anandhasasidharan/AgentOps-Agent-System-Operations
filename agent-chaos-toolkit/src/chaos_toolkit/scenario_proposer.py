from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.models import Experiment, Scenario

_SYSTEM_PROMPT_HEADER = (
    "You are a chaos engineering expert for AI agents. "
    "Given an agent's tool usage history and past experiment results, "
    "propose 3 NEW failure scenarios that would stress untested failure modes."
)
_SYSTEM_PROMPT_FMT = (
    "Return ONLY valid JSON matching this exact schema:\n"
    '{\n  "proposals": [\n    {\n'
    '      "name": "short-name-no-spaces",\n'
    '      "description": "What failure mode and why this scenario matters",\n'
    '      "target_type": "llm|tool|rag|mcp",\n'
    '      "failure_mode": "timeout|crash|bad_output|hallucination|'
    "refusal|model_downgrade|no_results|bad_data|"
    'corrupted_context|slow_response|server_down|auth_failure|wrong_data",\n'
    '      "config": {"params": {"delay_seconds": 0.5}},\n'
    '      "expected_behavior": "graceful_degradation|fail_fast|'
    'retry_success|fallback_used|error_handled",\n'
    '      "agent_should_survive": true\n    }\n  ]\n}\n\n'
    "Built-in scenarios exist for {existing_modes}. "
    "Do not repeat these. Propose scenarios for targets or "
    "failure modes the agent has NOT been tested against."
)

SYSTEM_PROMPT = _SYSTEM_PROMPT_HEADER + "\n\n" + _SYSTEM_PROMPT_FMT

_REFINE_PROMPT_HEADER = (
    "You are a chaos engineering expert refining failure scenarios. "
    "Given an agent's experiment outcomes, modify the previous proposals "
    "to be more challenging."
)
_REFINE_PROMPT_FMT = (
    "Rules:\n"
    "- Scenarios the agent SURVIVED: increase intensity "
    "(longer delays, more corrupted data, stricter auth)\n"
    "- Scenarios the agent FAILED: reduce intensity "
    "OR replace with different failure mode\n"
    "- Always propose 3 scenarios total\n"
    "- Do NOT repeat existing test coverage: {existing_modes}\n\n"
    "Return ONLY valid JSON matching this schema:\n"
    '{\n  "proposals": [\n    {\n'
    '      "name": "short-name-no-spaces",\n'
    '      "description": "What failure mode and why this scenario matters",\n'
    '      "target_type": "llm|tool|rag|mcp",\n'
    '      "failure_mode": "timeout|crash|bad_output|hallucination|'
    "refusal|model_downgrade|no_results|bad_data|"
    'corrupted_context|slow_response|server_down|auth_failure|wrong_data",\n'
    '      "config": {"params": {"delay_seconds": 0.5}},\n'
    '      "expected_behavior": "graceful_degradation|fail_fast|'
    'retry_success|fallback_used|error_handled",\n'
    '      "agent_should_survive": true\n    }\n  ]\n}'
)

REFINE_PROMPT = _REFINE_PROMPT_HEADER + "\n\n" + _REFINE_PROMPT_FMT


async def propose_scenarios(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str | None = None,
    model: str = "gpt-4o",
) -> list[dict[str, Any]]:
    context = await _build_context(session, tenant_id, agent_id)
    if not context["existing_modes"]:
        return []

    prompt = _build_prompt(context)
    proposals = await _call_llm(prompt, model)
    if proposals is None:
        return []

    validated = []
    for p in proposals:
        if p.get("target_type") in ("llm", "tool", "rag", "mcp") and p.get("failure_mode"):
            validated.append(p)
    return validated


async def _build_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str | None,
) -> dict[str, Any]:
    stmt = select(Scenario).where(Scenario.tenant_id == tenant_id)
    if agent_id:
        stmt = stmt.where(Scenario.enabled)
    result = await session.execute(stmt)
    scenarios = list(result.scalars().all())

    existing_modes = list({(s.target_type, s.failure_mode) for s in scenarios})
    existing_targets = list({s.target_type for s in scenarios})

    exp_stmt = (
        select(Experiment)
        .where(Experiment.tenant_id == tenant_id)
        .order_by(Experiment.created_at.desc())
        .limit(20)
    )
    if agent_id:
        exp_stmt = exp_stmt.where(Experiment.agent_id == agent_id)
    exp_result = await session.execute(exp_stmt)
    experiments = list(exp_result.scalars().all())

    survived = sum(1 for e in experiments if e.agent_survived)
    total = len(experiments)

    return {
        "existing_modes": existing_modes,
        "existing_targets": existing_targets,
        "agent_id": agent_id or "any",
        "total_experiments": total,
        "survival_rate": survived / total if total > 0 else 0.0,
    }


def _build_prompt(context: dict[str, Any]) -> str:
    existing_modes_str = (
        ", ".join(f"{t}/{m}" for t, m in context.get("existing_modes", [])) or "none"
    )

    header = (
        f"Agent: {context['agent_id']}\n"
        f"Existing test coverage: {existing_modes_str}\n"
        f"Previous experiments: {context['total_experiments']} runs, "
        f"survival rate: {context['survival_rate']:.0%}\n\n"
    )
    body = SYSTEM_PROMPT.replace("{existing_modes}", existing_modes_str)
    return header + body


async def refine_proposals(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    model: str = "gpt-4o",
) -> list[dict[str, Any]]:
    context = await _build_context(session, tenant_id, agent_id)
    if not context["existing_modes"]:
        return []

    exp_stmt = (
        select(Experiment)
        .where(Experiment.tenant_id == tenant_id, Experiment.agent_id == agent_id)
        .order_by(Experiment.created_at.desc())
        .limit(50)
    )
    exp_result = await session.execute(exp_stmt)
    experiments = list(exp_result.scalars().all())

    survived_modes: list[str] = []
    failed_modes: list[str] = []
    for e in experiments:
        label = f"{e.target_type}/{e.failure_mode}"
        if e.agent_survived:
            survived_modes.append(label)
        else:
            failed_modes.append(label)

    existing_modes_str = (
        ", ".join(f"{t}/{m}" for t, m in context.get("existing_modes", [])) or "none"
    )

    prompt = (
        f"Agent: {agent_id}\n"
        f"Scenarios survived ({len(survived_modes)}): "
        f"{', '.join(set(survived_modes)) or 'none'}\n"
        f"Scenarios failed ({len(failed_modes)}): "
        f"{', '.join(set(failed_modes)) or 'none'}\n"
        f"Total experiments: {len(experiments)}, "
        f"survival rate: "
        f"{sum(1 for e in experiments if e.agent_survived) / len(experiments):.0%}\n\n"
        f"{REFINE_PROMPT.replace('{existing_modes}', existing_modes_str)}"
    )

    proposals = await _call_llm(prompt, model)
    if proposals is None:
        return []

    validated = []
    for p in proposals:
        if p.get("target_type") in ("llm", "tool", "rag", "mcp") and p.get("failure_mode"):
            validated.append(p)
    return validated


async def _call_llm(prompt: str, model: str) -> list[dict[str, Any]] | None:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        content = resp.choices[0].message.content
        if not content:
            return None
        data = json.loads(content)
        return data.get("proposals", [])
    except Exception:
        return None
