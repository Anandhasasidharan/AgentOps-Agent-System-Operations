from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

experiments_total = Counter(
    "chaos_experiments_total",
    "Experiments completed",
    ["status", "target_type"],
)

experiment_duration_seconds = Histogram(
    "chaos_experiment_duration_seconds",
    "Experiment duration",
    ["target_type", "failure_mode"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

resilience_score = Gauge(
    "chaos_resilience_score", "Current resilience score (0-100)", ["tenant_id"]
)

scenarios_total = Gauge(
    "chaos_scenarios_total", "Number of scenarios configured", ["target_type", "tenant_id"]
)


def add_metrics_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
