from prometheus_client import Counter, Gauge, Histogram

events_published_total = Counter(
    "gw_events_published_total",
    "Events forwarded to WebSocket clients",
    ["event_type"],
)

ws_connections = Gauge("gw_ws_connections", "Current WebSocket connections")

events_buffer_size = Gauge("gw_events_buffer_size", "Events in ring buffer")

publish_duration_seconds = Histogram(
    "gw_publish_duration_seconds",
    "Time to publish event to WebSocket clients",
)

events_dropped_total = Counter(
    "events_dropped_total", "Events dropped due to failures", ["reason", "service"]
)
