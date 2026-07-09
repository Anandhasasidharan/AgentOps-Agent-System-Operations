from __future__ import annotations

import respx
import httpx
import pytest

from agentops_langchain import wrap_tool, AgentBlockedError, AgentOpsCallbackHandler


@respx.mock
def test_wrap_tool_allows():
    respx.post("http://localhost:8001/v1/intercept").respond(
        json={"allowed": True, "decision": "allow"}
    )

    def my_tool(x: str) -> str:
        return f"processed: {x}"

    wrapped = wrap_tool(my_tool, "my_tool", "test-key", "http://localhost:8001", "agent-1")
    result = wrapped("hello")
    assert result == "processed: hello"


@respx.mock
def test_wrap_tool_blocks():
    respx.post("http://localhost:8001/v1/intercept").respond(
        json={"allowed": False, "reason": "risk threshold exceeded"}
    )

    def my_tool(x: str) -> str:
        return "should not reach"

    wrapped = wrap_tool(my_tool, "my_tool", "test-key", "http://localhost:8001", "agent-1")
    with pytest.raises(AgentBlockedError, match="risk threshold exceeded"):
        wrapped("dangerous input")


@respx.mock
def test_wrap_tool_cb_unreachable():
    respx.post("http://localhost:8001/v1/intercept").mock(side_effect=httpx.RequestError("connection refused"))

    def my_tool(x: str) -> str:
        return "fallback result"

    wrapped = wrap_tool(my_tool, "my_tool", "test-key", "http://localhost:8001", "agent-1")
    result = wrapped("anything")
    assert result == "fallback result"


@pytest.mark.asyncio
@respx.mock
async def test_callback_on_tool_start_allows():
    respx.post("http://localhost:8001/v1/intercept").respond(
        json={"allowed": True, "decision": "allow"}
    )

    handler = AgentOpsCallbackHandler("test-key", "http://localhost:8001", agent_id="agent-1")
    await handler.on_tool_start(
        {"name": "search"}, "query data",
        run_id=None, tags=None, metadata=None,
    )
    await handler.close()


@pytest.mark.asyncio
@respx.mock
async def test_callback_on_tool_start_blocks():
    respx.post("http://localhost:8001/v1/intercept").respond(
        json={"allowed": False, "reason": "blocked by policy"}
    )

    handler = AgentOpsCallbackHandler("test-key", "http://localhost:8001", agent_id="agent-1")
    with pytest.raises(AgentBlockedError, match="blocked by policy"):
        await handler.on_tool_start(
            {"name": "exec"}, "rm -rf",
            run_id=None, tags=None, metadata=None,
        )
    await handler.close()


@pytest.mark.asyncio
@respx.mock
async def test_callback_cb_unreachable():
    respx.post("http://localhost:8001/v1/intercept").mock(side_effect=httpx.RequestError("timeout"))

    handler = AgentOpsCallbackHandler("test-key", "http://localhost:8001", agent_id="agent-1")
    await handler.on_tool_start(
        {"name": "search"}, "data",
        run_id=None, tags=None, metadata=None,
    )
    await handler.close()


@respx.mock
def test_wrap_tool_uses_correct_headers():
    respx.post("http://localhost:8001/v1/intercept").respond(
        json={"allowed": True, "decision": "allow"}
    )

    def my_tool(x: str) -> str:
        return "ok"

    wrapped = wrap_tool(my_tool, "test_tool", "my-api-key", "http://localhost:8001", "agent-1")
    wrapped("data")

    import json
    request = respx.calls.last.request
    assert request.headers["X-API-Key"] == "my-api-key"
    body = json.loads(request.content)
    assert body["agent_id"] == "agent-1"
    assert body["tool_name"] == "test_tool"
