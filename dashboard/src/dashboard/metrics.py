from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from fastapi import FastAPI

upstream_health = Gauge(
    "dash_upstream_health", "Upstream service health (1=up)",
    ["service"]
)

health_check_duration_seconds = Histogram(
    "dash_health_check_duration_seconds", "Health check duration",
    ["service"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)


def add_metrics_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
