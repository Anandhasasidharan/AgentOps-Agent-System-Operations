"""Condition schemas are the single source of truth for API and CLI policies."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from circuit_breaker.yaml_policy import parse_yaml

POLICY_TYPES_AND_TYPOS = [
    ("tool_allowlist", {"toolz": ["read_file"]}),
    ("tool_blocklist", {"toolz": ["delete_file"]}),
    ("rate_limit", {"max_call": 10}),
    ("token_budget", {"max_token": 1000}),
    ("risk_threshold", {"max_risk": 0.8}),
    ("anomaly_threshold", {"max_anomaly": 0.8}),
    ("time_window", {"startt": 1.0, "end": 2.0}),
    ("reasoning_loop", {"max_same_tool": 3}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("policy_type", "conditions"), POLICY_TYPES_AND_TYPOS)
async def test_api_rejects_misspelled_condition_key(
    client: AsyncClient,
    policy_type: str,
    conditions: dict,
) -> None:
    resp = await client.post(
        "/api/v1/policies",
        json={
            "name": f"typo-{policy_type}",
            "policy_type": policy_type,
            "conditions": conditions,
            "action": "block",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy_type", "conditions"),
    [
        ("tool_allowlist", {"tools": ["read_file"]}),
        ("tool_blocklist", {"tools": ["delete_file"]}),
        ("rate_limit", {"max_calls": 10}),
        ("token_budget", {"max_tokens": 1000}),
        ("risk_threshold", {"max_risk_score": 0.8}),
        ("anomaly_threshold", {"max_anomaly_score": 0.8}),
        ("time_window", {"start": 1.0, "end": 2.0}),
        ("reasoning_loop", {"max_consecutive_same_tool": 3}),
    ],
)
async def test_api_accepts_valid_conditions(
    client: AsyncClient,
    policy_type: str,
    conditions: dict,
) -> None:
    resp = await client.post(
        "/api/v1/policies",
        json={
            "name": f"valid-{policy_type}",
            "policy_type": policy_type,
            "conditions": conditions,
            "action": "block",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["conditions"] == conditions


@pytest.mark.parametrize(("policy_type", "conditions"), POLICY_TYPES_AND_TYPOS)
def test_yaml_rejects_misspelled_condition_key(policy_type: str, conditions: dict) -> None:
    content = f"""
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: typo-{policy_type}
spec:
  type: {policy_type}
  conditions: {conditions}
"""
    with pytest.raises(ValidationError):
        parse_yaml(content)


def test_yaml_accepts_camel_case_aliases() -> None:
    docs = parse_yaml(
        """
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: camel-case
spec:
  type: rate_limit
  conditions:
    maxCalls: 10
"""
    )
    assert docs[0].spec.conditions == {"max_calls": 10}


def test_yaml_rejects_cross_midnight_window() -> None:
    with pytest.raises(ValidationError):
        parse_yaml(
            """
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: cross-midnight
spec:
  type: time_window
  conditions:
    start: 22
    end: 3
"""
        )
