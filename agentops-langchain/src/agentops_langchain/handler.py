from __future__ import annotations

import logging
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


class AgentBlockedError(Exception):
    pass


def wrap_tool(
    tool_fn: Callable,
    tool_name: str,
    api_key: str,
    cb_url: str = "http://localhost:8001",
    agent_id: str = "langchain-agent",
) -> Callable:
    client = httpx.Client(timeout=10.0, headers={"X-API-Key": api_key})
    cb_url = cb_url.rstrip("/")

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            resp = client.post(
                f"{cb_url}/v1/intercept",
                json={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "tool_input": {"args": str(args), "kwargs": str(kwargs)},
                },
            )
            result = resp.json()
            if not result.get("allowed", True):
                raise AgentBlockedError(
                    f"Tool '{tool_name}' blocked: {result.get('reason', 'no reason')}"
                )
        except httpx.RequestError:
            logger.warning("CB unreachable, allowing tool")
        return tool_fn(*args, **kwargs)

    return wrapped


class AgentOpsCallbackHandler:
    def __init__(
        self,
        api_key: str,
        cb_url: str = "http://localhost:8001",
        slo_url: str = "http://localhost:8000",
        agent_id: str | None = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key
        self.cb_url = cb_url.rstrip("/")
        self.slo_url = slo_url.rstrip("/")
        self.agent_id = agent_id
        self._client = httpx.AsyncClient(timeout=timeout, headers={"X-API-Key": api_key})

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        agent_id = self.agent_id or (
            metadata.get("agent_id", "unknown") if metadata else "unknown"
        )
        try:
            resp = await self._client.post(
                f"{self.cb_url}/v1/intercept",
                json={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "tool_input": {"input": input_str},
                },
            )
            result = resp.json()
            if not result.get("allowed", True):
                raise AgentBlockedError(
                    f"Tool '{tool_name}' blocked: {result.get('reason', 'no reason')}"
                )
        except httpx.RequestError as e:
            logger.warning("CB unreachable, allowing tool: %s", e)

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        pass

    async def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        pass

    async def close(self):
        await self._client.aclose()
