"""Tests for risk-budget math."""

from agent_slo.risk_budget import build_risk_budget, consume_tool_call, evaluate_risk_budget


def test_build_risk_budget() -> None:
    config = {
        "budget": 5,
        "window": "1h",
        "weights": {"delete_file": 2, "send_email": 1},
        "action": "require_approval",
    }
    state = build_risk_budget(config)
    assert state.budget == 5
    assert state.weights["delete_file"] == 2
    assert state.action == "require_approval"


def test_consume_and_evaluate() -> None:
    state = build_risk_budget({
        "budget": 5,
        "window": "1h",
        "weights": {"delete_file": 2, "send_email": 1},
        "action": "kill",
    })
    consume_tool_call(state, "delete_file", None)
    consume_tool_call(state, "send_email", None)
    result = evaluate_risk_budget(state)
    assert result["consumed"] == 3
    assert result["remaining"] == 2
    assert result["action"] == "kill"
    assert result["exceeded"] is False

    # exceed budget
    consume_tool_call(state, "delete_file", None)
    consume_tool_call(state, "delete_file", None)
    result = evaluate_risk_budget(state)
    assert result["exceeded"] is True
