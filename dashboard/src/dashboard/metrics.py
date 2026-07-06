from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

upstream_health = Gauge("dash_upstream_health", "Upstream service health (1=up)", ["service"])

health_check_duration_seconds = Histogram(
    "dash_health_check_duration_seconds",
    "Health check duration",
    ["service"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

events_dropped_total = Counter(
    "events_dropped_total", "Events dropped due to failures", ["reason", "service"]
)


def add_metrics_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
