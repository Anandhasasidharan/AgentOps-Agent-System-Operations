"""Extract agent-native SLIs from OTel spans."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agent_slo.models import OtelSpan

KNOWN_ATTRIBUTES = {
    "gen_ai.system",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.prompt_tokens",
    "gen_ai.usage.completion_tokens",
    "gen_ai.usage.total_tokens",
    "gen_ai.eval.success",
    "gen_ai.eval.hallucination",
    "gen_ai.eval.total",
    "gen_ai.eval.trust_score",
    "gen_ai.eval.trust_supported",
    "gen_ai.eval.trust_unsupported",
    "gen_ai.eval.trust_contradictions",
    "gen_ai.eval.trust_checklist",
    "gen_ai.tool.name",
    "gen_ai.tool.success",
    "gen_ai.tool.calls",
    "gen_ai.response.id",
    "gen_ai.response.model",
    "gen_ai.response.finish_reasons",
    "agentops.agent.id",
    "agentops.environment",
    "agentops.risk_weight",
    "gen_ai.response.duration",
}


def parse_otlp_spans(payload: dict[str, Any], tenant_id: uuid.UUID) -> list[OtelSpan]:
    spans: list[OtelSpan] = []
    resource_spans = payload.get("resourceSpans", [])
    for rs in resource_spans:
        resource_attrs = _flatten_attrs(rs.get("resource", {}).get("attributes", []))
        for scope_span in rs.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                span_attrs = _flatten_attrs(span.get("attributes", []))
                span_attrs.update(resource_attrs)
                agent_id = _resolve_agent_id(span_attrs.get("agentops.agent.id"))
                spans.append(
                    OtelSpan(
                        trace_id=bytes.fromhex(span["traceId"]) if "traceId" in span else b"",
                        span_id=bytes.fromhex(span["spanId"]) if "spanId" in span else b"",
                        parent_span_id=(
                            bytes.fromhex(span["parentSpanId"])
                            if span.get("parentSpanId")
                            else None
                        ),
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        name=span.get("name", "unnamed"),
                        kind=span.get("kind", 0),
                        start_time=_nanos_to_datetime(span["startTimeUnixNano"]),
                        end_time=_nanos_to_datetime(span["endTimeUnixNano"]),
                        attributes=span_attrs,
                        events=span.get("events", []),
                        status=span.get("status", {}),
                    )
                )
    return spans


def _flatten_attrs(attrs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attr in attrs:
        key = attr.get("key")
        value = attr.get("value", {})
        if not key:
            continue
        # OTLP AnyValue: stringValue, intValue, doubleValue, boolValue, arrayValue, kvlistValue
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "intValue" in value:
            result[key] = int(value["intValue"])
        elif "doubleValue" in value:
            result[key] = float(value["doubleValue"])
        elif "boolValue" in value:
            result[key] = bool(value["boolValue"])
        elif "arrayValue" in value:
            arr = value["arrayValue"].get("values", [])
            result[key] = [_resolve_any_value(v) for v in arr]
    return result


def _resolve_any_value(v: dict[str, Any]) -> Any:
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in v:
            return v[key]
    return None


def _resolve_agent_id(agent_ref: Any) -> uuid.UUID | None:
    if not agent_ref:
        return None
    if isinstance(agent_ref, uuid.UUID):
        return agent_ref
    try:
        return uuid.UUID(str(agent_ref))
    except ValueError:
        # In v1 we require agent_id as UUID in attributes; name-based lookup is future work.
        return None


def _nanos_to_datetime(nanos: int | str) -> datetime:
    if isinstance(nanos, str):
        nanos = int(nanos)
    return datetime.fromtimestamp(nanos / 1e9)


def extract_sli_metrics(span: OtelSpan) -> dict[str, float]:
    """Extract numeric SLI signals from a single span."""
    attrs = span.attributes
    metrics: dict[str, float] = {}

    if "gen_ai.eval.success" in attrs:
        metrics["task_success"] = float(attrs["gen_ai.eval.success"])
    if "gen_ai.eval.hallucination" in attrs:
        metrics["hallucination"] = float(attrs["gen_ai.eval.hallucination"])
    if "gen_ai.eval.total" in attrs:
        metrics["eval_total"] = float(attrs["gen_ai.eval.total"])
    if "gen_ai.tool.success" in attrs:
        metrics["tool_success"] = float(attrs["gen_ai.tool.success"])
    if "gen_ai.tool.calls" in attrs:
        metrics["tool_calls"] = float(attrs["gen_ai.tool.calls"])
    if "gen_ai.usage.input_tokens" in attrs:
        metrics["input_tokens"] = float(attrs["gen_ai.usage.input_tokens"])
    if "gen_ai.usage.output_tokens" in attrs:
        metrics["output_tokens"] = float(attrs["gen_ai.usage.output_tokens"])
    if "gen_ai.usage.prompt_tokens" in attrs:
        metrics["prompt_tokens"] = float(attrs["gen_ai.usage.prompt_tokens"])
    if "gen_ai.usage.completion_tokens" in attrs:
        metrics["completion_tokens"] = float(attrs["gen_ai.usage.completion_tokens"])
    if "gen_ai.usage.total_tokens" in attrs:
        metrics["total_tokens"] = float(attrs["gen_ai.usage.total_tokens"])
    if "gen_ai.response.duration" in attrs:
        metrics["latency_ms"] = float(attrs["gen_ai.response.duration"])
    if "agentops.risk_weight" in attrs:
        metrics["risk_weight"] = float(attrs["agentops.risk_weight"])
    if "gen_ai.eval.trust_score" in attrs:
        metrics["trust_score"] = float(attrs["gen_ai.eval.trust_score"])

    return metrics
