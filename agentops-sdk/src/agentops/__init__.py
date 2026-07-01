"""Unified Python client for the AgentOps platform.

Usage:
    from agentops import AgentOpsSDK

    sdk = AgentOpsSDK(api_key="acme-corp")
    sdk.intercept(tool_name="read_file", tool_input={"path": "/tmp/x"})
    sdk.record_metric("task_success_rate", 0.95)
    sdk.run_chaos_experiment(scenario_id="...")
"""

from agentops.client import AgentOpsSDK

__all__ = ["AgentOpsSDK"]
