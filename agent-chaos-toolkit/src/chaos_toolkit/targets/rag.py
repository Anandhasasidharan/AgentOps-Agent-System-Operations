"""RAG target — inject failures into RAG retrieval.

Failure modes:
  - no_results: Empty retrieval results
  - bad_data: Return irrelevant or misleading context
  - corrupted_context: Return garbled/truncated context
  - slow_response: Extremely slow retrieval
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

FAILURE_MODES = ["no_results", "bad_data", "corrupted_context", "slow_response"]


async def inject_rag_fault(
    config: dict[str, Any],
    agent_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failure_mode = config.get("failure_mode", "no_results")
    params = config.get("params", {})

    if failure_mode == "no_results":
        return _simulate_no_results(params)
    elif failure_mode == "bad_data":
        return _simulate_bad_data(params)
    elif failure_mode == "corrupted_context":
        return _simulate_corrupted_context(params)
    elif failure_mode == "slow_response":
        return await _simulate_slow_response(params)
    else:
        raise ValueError(f"Unknown RAG failure mode: {failure_mode}")


def _simulate_no_results(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fault_injected": True,
        "failure_mode": "no_results",
        "retrieved_chunks": [],
        "total_chunks": 0,
        "error": None,
        "message": "RAG retrieval returned no results",
    }


def _simulate_bad_data(params: dict[str, Any]) -> dict[str, Any]:
    irrelevant_content = params.get(
        "irrelevant_content",
        "The recipe for chocolate chip cookies requires 2 cups of flour, "
        "1 cup of sugar, and a pinch of salt. Bake at 350F for 12 minutes.",
    )
    return {
        "fault_injected": True,
        "failure_mode": "bad_data",
        "retrieved_chunks": [
            {"id": "irrelevant-1", "content": irrelevant_content, "relevance": 0.02}
        ],
        "total_chunks": 1,
        "message": "RAG returned irrelevant context",
    }


def _simulate_corrupted_context(params: dict[str, Any]) -> dict[str, Any]:
    corrupted_content = params.get(
        "corrupted_content",
        "��\x00\x00\x00\x19t\x00h\x00i\x00s\x00 \x00i\x00s\x00 \x00c\x00o\x00r\x00r\x00u\x00p\x00t\x00e\x00d\x00 \x00d\x00a\x00t\x00a",  # noqa: E501
    )
    return {
        "fault_injected": True,
        "failure_mode": "corrupted_context",
        "retrieved_chunks": [
            {"id": "corrupted-1", "content": corrupted_content, "encoding": "utf-8"}
        ],
        "message": "RAG returned corrupted context data",
    }


async def _simulate_slow_response(params: dict[str, Any]) -> dict[str, Any]:
    delay = params.get("delay_seconds", random.uniform(15, 60))
    await asyncio.sleep(delay)
    return {
        "fault_injected": True,
        "failure_mode": "slow_response",
        "retrieved_chunks": [
            {
                "id": "chunk-1",
                "content": "This is a valid but very slow response.",
                "relevance": 0.85,
            }
        ],
        "response_time_s": delay,
        "message": f"RAG retrieval took {delay:.1f}s",
    }
