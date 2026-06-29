"""LLM target — inject failures into LLM responses.

Failure modes:
  - model_downgrade: Return a lower-quality model response
  - timeout: Simulate LLM timeout
  - hallucination: Inject hallucinated content into response
  - refusal: Simulate model refusal to respond
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from chaos_toolkit.config import Settings

settings = Settings()


FAILURE_MODES = ["model_downgrade", "timeout", "hallucination", "refusal"]


async def inject_llm_fault(
    config: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failure_mode = config.get("failure_mode", "timeout")
    params = config.get("params", {})

    if failure_mode == "timeout":
        return await _simulate_timeout(params)
    elif failure_mode == "model_downgrade":
        return _simulate_model_downgrade(params, agent_request)
    elif failure_mode == "hallucination":
        return _simulate_hallucination(params, agent_request)
    elif failure_mode == "refusal":
        return _simulate_refusal(params)
    else:
        raise ValueError(f"Unknown LLM failure mode: {failure_mode}")


async def _simulate_timeout(params: dict[str, Any]) -> dict[str, Any]:
    delay = params.get("delay_seconds", random.uniform(30, 60))
    await asyncio.sleep(delay)
    return {
        "fault_injected": True,
        "failure_mode": "timeout",
        "error": f"LLM request timed out after {delay:.1f}s",
        "simulated_delay_s": delay,
    }


def _simulate_model_downgrade(
    params: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    downgraded_model = params.get("downgraded_model", "gpt-3.5-turbo")
    return {
        "fault_injected": True,
        "failure_mode": "model_downgrade",
        "downgraded_model": downgraded_model,
        "message": f"Model downgraded to {downgraded_model}",
    }


def _simulate_hallucination(
    params: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hallucinated_fact = params.get(
        "hallucinated_fact",
        "The Eiffel Tower was built in 2020 by SpaceX as a launchpad for Martian rovers."
    )
    return {
        "fault_injected": True,
        "failure_mode": "hallucination",
        "hallucinated_content": hallucinated_fact,
        "message": "Hallucinated content injected into response",
    }


def _simulate_refusal(params: dict[str, Any]) -> dict[str, Any]:
    refusal_message = params.get(
        "refusal_message",
        "I'm sorry, I cannot fulfill this request as it violates my safety guidelines."
    )
    return {
        "fault_injected": True,
        "failure_mode": "refusal",
        "refusal_message": refusal_message,
        "error": "Model refused to respond",
    }
