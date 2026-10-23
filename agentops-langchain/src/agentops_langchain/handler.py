from __future__ import annotations

from typing import Any, Callable

import httpx

from agentops_langchain.fail_mode import (
    FAIL_CLOSED,
    log_degraded_decision,
    resolve_fail_mode,
)


class AgentBlockedError(Exception):
    pass


class AgentOpsUnavailableError(AgentBlockedError):
    """Raised when the breaker is unreachable and fail mode is closed."""


def _degraded(
    *,
    operation: str,
    fail_mode: str,
    exc: Exception,
    agent_id: str,
    tool_name: str,
) -> None:
    reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    log_degraded_decision(
        service="agentops-langchain",
        operation=operation,
        fail_mode=fail_mode,
        reason=reason,
        agent_id=agent_id,
        tool_name=tool_name,
    )
    if fail_mode == FAIL_CLOSED:
        raise AgentOpsUnavailableError(
            f"AgentOps Circuit Breaker unavailable during {operation}; failing closed"
        ) from exc


def _parse_verdict(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or "allowed" not in result:
        raise ValueError("intercept response is missing the 'allowed' field")
    return result


def wrap_tool(
    tool_fn: Callable,
    tool_name: str,
    api_key: str,
    cb_url: str = "http://localhost:8001",
    agent_id: str = "langchain-agent",
    fail_mode: str | None = None,
) -> Callable:
    client = httpx.Client(timeout=10.0, headers={"X-API-Key": api_key})
    cb_url = cb_url.rstrip("/")
    mode = resolve_fail_mode(fail_mode)

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
            result = _parse_verdict(resp)
        except (httpx.HTTPError, ValueError) as exc:
            _degraded(
                operation="wrap_tool",
                fail_mode=mode,
                exc=exc,
                agent_id=agent_id,
                tool_name=tool_name,
            )
        else:
            if not result["allowed"]:
                raise AgentBlockedError(
                    f"Tool '{tool_name}' blocked: {result.get('reason', 'no reason')}"
                )
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
        fail_mode: str | None = None,
    ):
        self.api_key = api_key
        self.cb_url = cb_url.rstrip("/")
        self.slo_url = slo_url.rstrip("/")
        self.agent_id = agent_id
        self.fail_mode = resolve_fail_mode(fail_mode)
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
        agent_id = self.agent_id or (metadata.get("agent_id", "unknown") if metadata else "unknown")
        try:
            resp = await self._client.post(
                f"{self.cb_url}/v1/intercept",
                json={
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "tool_input": {"input": input_str},
                },
            )
            result = _parse_verdict(resp)
        except (httpx.HTTPError, ValueError) as exc:
            _degraded(
                operation="callback.on_tool_start",
                fail_mode=self.fail_mode,
                exc=exc,
                agent_id=agent_id,
                tool_name=tool_name,
            )
        else:
            if not result["allowed"]:
                raise AgentBlockedError(
                    f"Tool '{tool_name}' blocked: {result.get('reason', 'no reason')}"
                )

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
