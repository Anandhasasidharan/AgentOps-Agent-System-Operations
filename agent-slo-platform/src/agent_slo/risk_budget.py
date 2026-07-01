"""Risk-budget SLO math."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agent_slo.yaml_spec import window_to_seconds


@dataclass
class RiskBudgetState:
    budget: float
    window_seconds: int
    weights: dict[str, float]
    action: str
    consumed: float = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.consumed)

    @property
    def consumed_fraction(self) -> float:
        if self.budget <= 0:
            return 0.0
        return min(1.0, self.consumed / self.budget)


def build_risk_budget(config: dict[str, Any]) -> RiskBudgetState:
    return RiskBudgetState(
        budget=float(config["budget"]),
        window_seconds=window_to_seconds(config["window"]),
        weights={k: float(v) for k, v in config.get("weights", {}).items()},
        action=config.get("action", "require_approval"),
    )


def consume_tool_call(state: RiskBudgetState, tool_name: str, timestamp: datetime) -> float:
    weight = state.weights.get(tool_name, 0.0)
    state.consumed += weight
    return state.consumed


def evaluate_risk_budget(state: RiskBudgetState) -> dict[str, Any]:
    return {
        "budget": state.budget,
        "consumed": state.consumed,
        "remaining": state.remaining,
        "consumed_fraction": state.consumed_fraction,
        "action": state.action,
        "exceeded": state.consumed >= state.budget,
    }
