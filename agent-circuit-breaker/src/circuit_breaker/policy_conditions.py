"""Typed policy condition schemas.

This module is the single source of truth for the ``conditions`` object used by
both the HTTP API and ``cbctl apply``. Unknown keys are rejected so a typo can
no longer create a policy that loads, reports as enabled, and silently never
matches. See ``docs/POLICY_SEMANTICS.md`` for the evaluated semantics.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.alias_generators import to_camel

__all__ = [
    "PolicyConditionsError",
    "validate_conditions",
    "CONDITION_MODELS",
    "ToolAllowlistConditions",
    "ToolBlocklistConditions",
    "RateLimitConditions",
    "TokenBudgetConditions",
    "RiskThresholdConditions",
    "AnomalyThresholdConditions",
    "TimeWindowConditions",
    "ReasoningLoopConditions",
]

ToolPattern = Annotated[str, Field(min_length=1, max_length=256)]
PolicyType = Literal[
    "tool_allowlist",
    "tool_blocklist",
    "rate_limit",
    "token_budget",
    "risk_threshold",
    "anomaly_threshold",
    "time_window",
    "reasoning_loop",
]


class PolicyConditionsError(ValueError):
    """Raised when a policy's conditions do not match its policy type."""


class _Conditions(BaseModel):
    """Common options shared by every policy type.

    ``agent_id`` scopes a policy to one agent. It is optional so existing
    tenant-wide policies keep their current behavior.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    agent_id: str | None = Field(default=None, min_length=1, max_length=128)


class ToolAllowlistConditions(_Conditions):
    tools: list[ToolPattern] = Field(..., min_length=1, max_length=64)


class ToolBlocklistConditions(_Conditions):
    tools: list[ToolPattern] = Field(..., min_length=1, max_length=64)


class RateLimitConditions(_Conditions):
    max_calls: int = Field(..., ge=1, le=4096)


class TokenBudgetConditions(_Conditions):
    max_tokens: int = Field(..., ge=1)


class RiskThresholdConditions(_Conditions):
    max_risk_score: float = Field(..., ge=0.0, le=1.0)


class AnomalyThresholdConditions(_Conditions):
    max_anomaly_score: float = Field(..., ge=0.0, le=1.0)


class TimeWindowConditions(_Conditions):
    start: float = Field(..., ge=0.0, le=24.0)
    end: float = Field(..., ge=0.0, le=24.0)

    @model_validator(mode="after")
    def _ordered_window(self) -> TimeWindowConditions:
        # Cross-midnight windows are deliberately unsupported (see
        # docs/POLICY_SEMANTICS.md). Rejecting them here keeps that limitation
        # explicit instead of silently never matching.
        if self.start > self.end:
            raise ValueError("start must be less than or equal to end")
        return self


class ReasoningLoopConditions(_Conditions):
    max_consecutive_same_tool: int = Field(default=5, ge=1)


CONDITION_MODELS: dict[str, type[_Conditions]] = {
    "tool_allowlist": ToolAllowlistConditions,
    "tool_blocklist": ToolBlocklistConditions,
    "rate_limit": RateLimitConditions,
    "token_budget": TokenBudgetConditions,
    "risk_threshold": RiskThresholdConditions,
    "anomaly_threshold": AnomalyThresholdConditions,
    "time_window": TimeWindowConditions,
    "reasoning_loop": ReasoningLoopConditions,
}


def validate_conditions(policy_type: str, conditions: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize conditions for a policy type.

    Returns a snake_case dictionary with unknown keys removed by rejection.
    Raises :class:`PolicyConditionsError` for an unknown policy type and a
    ``pydantic.ValidationError`` for invalid conditions.
    """

    model = CONDITION_MODELS.get(policy_type)
    if model is None:
        raise PolicyConditionsError(f"Unknown policy type: {policy_type}")
    try:
        parsed = model.model_validate(conditions or {})
    except ValidationError as exc:
        raise PolicyConditionsError(_format_error(policy_type, exc)) from exc
    return parsed.model_dump(exclude_none=True)


def _format_error(policy_type: str, exc: ValidationError) -> str:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}")
    return f"Invalid conditions for {policy_type}: " + "; ".join(details)
