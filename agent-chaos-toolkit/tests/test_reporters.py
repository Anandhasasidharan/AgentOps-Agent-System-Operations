"""Tests for CI reporters."""

import uuid

from chaos_toolkit.models import Experiment
from chaos_toolkit.reporters.ci import generate_github_actions_summary, generate_junit_xml


def _make_experiment(score: float, survived: bool = True) -> Experiment:
    return Experiment(
        tenant_id=uuid.uuid4(),
        scenario_id=uuid.uuid4(),
        scenario_name="test-scenario",
        target_type="llm",
        failure_mode="timeout",
        agent_id="agent-1",
        status="completed",
        injection_successful=True,
        agent_survived=survived,
        resilience_score=score,
    )


def test_junit_xml_all_pass():
    exps = [_make_experiment(1.0), _make_experiment(0.9)]
    xml = generate_junit_xml(exps)
    assert '<testsuite name="agent-chaos-toolkit" tests="2">' in xml
    assert "<testcase" in xml
    assert '<failure' not in xml


def test_junit_xml_with_failures():
    exps = [_make_experiment(1.0), _make_experiment(0.3)]
    xml = generate_junit_xml(exps)
    assert '<failure' in xml
    assert "Resilience failure" in xml or "ResilienceFailure" in xml


def test_github_summary():
    exps = [_make_experiment(1.0), _make_experiment(0.3)]
    lines = generate_github_actions_summary(exps)
    summary = "\n".join(lines)
    assert "Agent Chaos Toolkit Results" in summary
    assert "✅" in summary
    assert "❌" in summary
    assert "1/2" in summary
