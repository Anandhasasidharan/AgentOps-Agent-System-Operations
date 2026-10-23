"""Python reference-engine tests.

The Python engine is the test oracle for the C engine in M5.
"""

from __future__ import annotations

from agentops_engine import AoCall, PyEngine, compile_policy_yaml

BLOCKLIST_YAML = """
apiVersion: agentops.io/v1
kind: Policy
metadata:
  name: block-dangerous
spec:
  type: tool_blocklist
  priority: 10
  conditions:
    tools: [delete_file]
  action:
    action: block
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
    max_calls: 2
  action:
    action: block
"""


def _call(agent_id: str = "agent-1", tool: str = "read_file") -> AoCall:
    return AoCall(
        agent_id=agent_id,
        tool=tool,
        input="{}",
        tokens=10,
        cost_micro=0,
        now_ns=0,
        minute_of_day=0,
        weekday=0,
    )


def test_pyengine_blocks_blocklisted_tool() -> None:
    engine = PyEngine()
    engine.load_policy(compile_policy_yaml(BLOCKLIST_YAML))

    assert engine.intercept(_call(tool="delete_file")).verdict == 2
    assert engine.intercept(_call(tool="read_file")).verdict == 0


def test_pyengine_rate_limit_is_stateful_per_agent() -> None:
    engine = PyEngine()
    engine.load_policy(compile_policy_yaml(RATE_LIMIT_YAML))

    assert engine.intercept(_call(agent_id="a")).verdict == 0
    assert engine.intercept(_call(agent_id="a")).verdict == 2
    # A different agent has its own counter.
    assert engine.intercept(_call(agent_id="b")).verdict == 0


def test_loading_a_policy_resets_state() -> None:
    engine = PyEngine()
    blob = compile_policy_yaml(RATE_LIMIT_YAML)
    engine.load_policy(blob)
    engine.intercept(_call(agent_id="a"))
    engine.intercept(_call(agent_id="a"))

    engine.load_policy(blob)
    assert engine.intercept(_call(agent_id="a")).verdict == 0
