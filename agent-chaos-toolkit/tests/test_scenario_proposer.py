from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from chaos_toolkit.models import Experiment, Scenario
from chaos_toolkit.scenario_proposer import (
    _build_context,
    _build_prompt,
    propose_scenarios,
)

TEST_TENANT = uuid.uuid4()


@pytest.fixture
async def sample_data(session: AsyncSession):
    for i in range(3):
        session.add(Scenario(
            tenant_id=TEST_TENANT, name=f"scenario-{i}",
            target_type="llm", failure_mode="timeout",
            expected_behavior="graceful_degradation",
        ))
        session.add(Experiment(
            tenant_id=TEST_TENANT, scenario_id=uuid.uuid4(),
            scenario_name=f"exp-{i}", target_type="llm",
            failure_mode="timeout", agent_id="agent-1",
            status="completed", agent_survived=i < 2,
            resilience_score=0.7,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))
    return session


class TestBuildContext:
    async def test_builds_context_with_existing_modes(self, session: AsyncSession, sample_data):
        ctx = await _build_context(session, TEST_TENANT, "agent-1")
        assert len(ctx["existing_modes"]) > 0
        assert ctx["total_experiments"] == 3
        assert ctx["survival_rate"] > 0

    async def test_empty_tenant(self, session: AsyncSession):
        ctx = await _build_context(session, uuid.uuid4(), None)
        assert ctx["total_experiments"] == 0
        assert ctx["survival_rate"] == 0.0


class TestBuildPrompt:
    def test_prompt_contains_context(self):
        ctx = {
            "existing_modes": [("llm", "timeout"), ("tool", "crash")],
            "existing_targets": ["llm", "tool"],
            "agent_id": "agent-1",
            "total_experiments": 10,
            "survival_rate": 0.8,
        }
        prompt = _build_prompt(ctx)
        assert "agent-1" in prompt
        assert "llm/timeout" in prompt
        assert "tool/crash" in prompt
        assert "10" in prompt


class TestRefineProposals:
    async def test_returns_empty_without_data(self, session: AsyncSession):
        from chaos_toolkit.scenario_proposer import refine_proposals
        result = await refine_proposals(session, uuid.uuid4(), "agent-1")
        assert result == []

    async def test_fallback_on_llm_failure(self, session: AsyncSession, sample_data):
        from chaos_toolkit.scenario_proposer import refine_proposals
        result = await refine_proposals(session, TEST_TENANT, "agent-1")
        assert isinstance(result, list)


class TestProposeScenarios:
    async def test_returns_empty_when_no_existing_modes(self, session: AsyncSession):
        result = await propose_scenarios(session, uuid.uuid4())
        assert result == []

    async def test_fallback_on_llm_failure(self, session: AsyncSession, sample_data):
        """With no OPENAI_API_KEY, _call_llm returns None gracefully."""
        result = await propose_scenarios(session, TEST_TENANT, "agent-1")
        assert isinstance(result, list)
