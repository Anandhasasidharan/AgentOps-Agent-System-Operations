from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from starlette.responses import Response

sli_requests_total = Counter(
    "slo_sli_requests_total", "SLI evaluation requests", ["sli_name", "metric_type"]
)

slo_current_value = Gauge("slo_current_value", "Current SLO value (0-1)", ["slo_name"])

slo_target = Gauge("slo_target", "SLO target value (0-1)", ["slo_name"])

slo_burn_rate = Gauge("slo_burn_rate", "SLO burn rate", ["slo_name"])

slo_budget_remaining = Gauge("slo_budget_remaining", "Error budget remaining (0-1)", ["slo_name"])

slo_breaching = Gauge("slo_breaching", "SLO is in breach (1=breaching)", ["slo_name"])

slo_alerts_total = Counter("slo_alerts_total", "Alerts fired", ["severity", "slo_name"])

otel_spans_ingested_total = Counter("slo_otel_spans_ingested_total", "OTel spans ingested")


def add_metrics_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
