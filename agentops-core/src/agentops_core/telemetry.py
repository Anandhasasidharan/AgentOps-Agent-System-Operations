from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


def _make_otlp_span(
    agent_id: str,
    tool_name: str,
    blocked: bool,
    duration_ms: float | None,
    token_count: int | None,
    risk_score: float | None,
) -> dict:
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    attrs = [
        {"key": "agentops.agent.id", "value": {"stringValue": agent_id}},
        {"key": "gen_ai.tool.name", "value": {"stringValue": tool_name}},
        {"key": "gen_ai.tool.success", "value": {"intValue": "0" if blocked else "1"}},
        {"key": "gen_ai.tool.calls", "value": {"intValue": "1"}},
    ]
    if duration_ms is not None:
        attrs.append({"key": "gen_ai.response.duration", "value": {"doubleValue": duration_ms}})
    if token_count is not None:
        attrs.append({"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(token_count)}})
        attrs.append({"key": "gen_ai.usage.output_tokens", "value": {"intValue": "0"}})
    if risk_score is not None:
        attrs.append({"key": "agentops.risk_weight", "value": {"doubleValue": risk_score}})

    return {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "agentops.circuit-breaker"},
                        "spans": [
                            {
                                "traceId": uuid.uuid4().hex,
                                "spanId": uuid.uuid4().hex[:16],
                                "name": f"tool_call.{tool_name}",
                                "kind": 2,
                                "startTimeUnixNano": now_ns,
                                "endTimeUnixNano": now_ns + int((duration_ms or 0) * 1e6),
                                "attributes": attrs,
                                "events": [],
                                "status": {"code": 0 if not blocked else 1},
                            }
                        ],
                    }
                ],
            }
        ]
    }


async def emit_tool_call_span(
    endpoint: str,
    api_key: str,
    agent_id: str,
    tool_name: str,
    blocked: bool,
    duration_ms: float | None = None,
    token_count: int | None = None,
    risk_score: float | None = None,
) -> None:
    if not endpoint:
        return
    if not api_key:
        logger.warning(
            "Telemetry export skipped: no credentials",
            extra={"event": "agentops.telemetry_export_failed", "reason": "missing_credentials"},
        )
        return
    payload = _make_otlp_span(agent_id, tool_name, blocked, duration_ms, token_count, risk_score)
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            response = await client.post(endpoint, json=payload, headers={"X-API-Key": api_key})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Never log request headers, URLs, payloads, or exception messages.
            response = getattr(exc, "response", None)
            logger.warning(
                "Telemetry export failed",
                extra={
                    "event": "agentops.telemetry_export_failed",
                    "reason": type(exc).__name__,
                    "status_code": response.status_code if response is not None else None,
                },
            )
