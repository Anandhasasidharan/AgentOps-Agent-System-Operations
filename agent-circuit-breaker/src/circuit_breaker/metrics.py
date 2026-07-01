from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

tool_calls_total = Counter(
    "cb_tool_calls_total",
    "Tool calls processed",
    ["verdict", "tool_name"],
)

tool_duration_seconds = Histogram(
    "cb_tool_duration_seconds",
    "Tool call duration",
    ["verdict", "tool_name"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

policies_total = Gauge("cb_policies_total", "Number of active policies", ["tenant_id"])

kill_switches_active = Gauge(
    "cb_kill_switches_active", "Active kill switches", ["agent_id", "tenant_id"]
)

incidents_total = Counter("cb_incidents_total", "Incidents created", ["severity", "category"])


def add_metrics_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
