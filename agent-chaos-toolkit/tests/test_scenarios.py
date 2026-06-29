"""Tests for scenarios engine."""

import uuid

import pytest

from chaos_toolkit.models import Scenario
from chaos_toolkit.scenarios import BUILTIN_SCENARIOS, seed_builtin_scenarios


class TestBuiltinScenarios:
    def test_builtin_scenarios_have_all_targets(self):
        targets = {s["target_type"] for s in BUILTIN_SCENARIOS}
        assert "llm" in targets
        assert "tool" in targets
        assert "rag" in targets
        assert "mcp" in targets

    def test_all_scenarios_have_required_fields(self):
        for s in BUILTIN_SCENARIOS:
            assert s["name"]
            assert s["target_type"] in ("llm", "tool", "rag", "mcp")
            assert s["failure_mode"]
            assert s["expected_behavior"]
            assert isinstance(s["agent_should_survive"], bool)

    def test_15_builtin_scenarios(self):
        assert len(BUILTIN_SCENARIOS) == 15


@pytest.mark.asyncio
async def test_seed_builtin_scenarios(session):
    tenant_id = uuid.uuid4()
    created = await seed_builtin_scenarios(session, tenant_id)
    assert len(created) == len(BUILTIN_SCENARIOS)

    # Second call should create none (already exist)
    created2 = await seed_builtin_scenarios(session, tenant_id)
    assert len(created2) == 0


@pytest.mark.asyncio
async def test_seeded_scenarios_have_correct_tenant(session):
    tenant_id = uuid.uuid4()
    await seed_builtin_scenarios(session, tenant_id)

    from sqlalchemy import select
    result = await session.execute(
        select(Scenario).where(Scenario.tenant_id == tenant_id)
    )
    scenarios = result.scalars().all()
    assert all(s.tenant_id == tenant_id for s in scenarios)
