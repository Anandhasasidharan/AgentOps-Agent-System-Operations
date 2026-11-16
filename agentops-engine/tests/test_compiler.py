"""Compiler and blob-format tests for the native engine package."""

from __future__ import annotations

import uuid

import pytest

from agentops_engine import PolicyCompileError, compile_policy_models, compile_policy_yaml, parse_blob

BLOCKLIST_YAML = """
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: block-dangerous
spec:
  type: tool_blocklist
  priority: 10
  conditions:
    tools: [delete_file, execute_command]
  action:
    action: block
---
"""

RATE_LIMIT_YAML = """
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: rate-limit
spec:
  type: rate_limit
  priority: 5
  conditions:
    max_calls: 10
  action:
    action: block
---
"""


def test_compile_yaml_round_trips_through_parse_blob() -> None:
    blob = compile_policy_yaml(BLOCKLIST_YAML)
    policies = parse_blob(blob)
    assert len(policies) == 1
    type_id, action_id, body = policies[0]
    assert type_id == 2  # tool_blocklist
    assert action_id == 1  # block
    assert body


def test_compile_sorts_by_priority_descending() -> None:
    blob = compile_policy_yaml(BLOCKLIST_YAML + RATE_LIMIT_YAML)
    policies = parse_blob(blob)
    assert [p[0] for p in policies] == [2, 3]


def test_corrupt_blob_is_rejected() -> None:
    blob = bytearray(compile_policy_yaml(BLOCKLIST_YAML))
    blob[-1] ^= 0xFF
    with pytest.raises(PolicyCompileError):
        parse_blob(bytes(blob))


def test_compile_policy_models() -> None:
    from circuit_breaker.models import Policy

    policy = Policy(
        tenant_id=uuid.uuid4(),
        name="block-rm",
        policy_type="tool_blocklist",
        conditions={"tools": ["rm"]},
        action="block",
        priority=1,
    )
    blob = compile_policy_models([policy])
    assert len(parse_blob(blob)) == 1
