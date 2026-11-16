from __future__ import annotations

import json
import logging
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from agentops_events import ALL_TOPICS, AgentOpsEvent, create_nats_client
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest

from .config import Settings
from .metrics import (
    events_buffer_size,
    events_dropped_total,
    events_published_total,
    ws_connections,
)

logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await listen_nats()
    yield
    if nats_conn:
        await nats_conn.close()


app = FastAPI(title="AgentOps Gateway", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

nats_conn = None
event_buffer: deque[dict] = deque(maxlen=settings.event_buffer_size)
ws_clients: dict[WebSocket, str] = {}


async def _validate_key(api_key: str) -> str | None:
    if not api_key:
        return None
    slo_url = settings.slo_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{slo_url}/api/v1/tenants/me", headers={"X-API-Key": api_key}
            )
            response.raise_for_status()
            tenant_id = response.json().get("id")
            return str(tenant_id) if tenant_id else None
    except (httpx.HTTPError, ValueError, AttributeError):
        return None


async def broadcast(event: AgentOpsEvent):
    data = json.loads(event.model_dump_json())
    event_buffer.append(data)
    events_buffer_size.set(len(event_buffer))
    dead: list[WebSocket] = []
    for ws, tenant_id in list(ws_clients.items()):
        if tenant_id != str(event.tenant_id):
            continue
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.pop(ws, None)
    if dead:
        events_dropped_total.labels(reason="dead_client", service="gateway").inc(len(dead))
    ws_connections.set(len(ws_clients))
    events_published_total.labels(event_type=event.event_type).inc()


async def nats_handler(msg):
    try:
        data = json.loads(msg.data.decode())
        event = AgentOpsEvent(**data)
        await broadcast(event)
    except Exception:
        logger.exception("error handling NATS message")
        events_dropped_total.labels(reason="parse_failed", service="gateway").inc()


async def listen_nats():
    global nats_conn
    nc = await create_nats_client(settings.nats_url)
    if nc is None:
        logger.warning("gateway running without NATS — no real-time events")
        return
    nats_conn = nc
    for topic in ALL_TOPICS:
        await nc.subscribe(topic, cb=nats_handler)
        logger.info("subscribed to %s", topic)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "nats_connected": nats_conn is not None and nats_conn.is_connected,
        "ws_clients": len(ws_clients),
        "buffered_events": len(event_buffer),
    }


@app.get("/metrics")
async def metrics():
    return generate_latest()


@app.get("/api/v1/events")
async def get_events(
    since: str | None = None, x_api_key: str = Header(default="", alias="X-API-Key")
):
    tenant_id = await _validate_key(x_api_key)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    result = [e for e in event_buffer if str(e["tenant_id"]) == tenant_id]
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return JSONResponse({"error": "invalid since format, use ISO 8601"}, status_code=400)
        result = [e for e in result if datetime.fromisoformat(e["timestamp"]) >= since_dt]
    return result


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, api_key: str | None = None):
    tenant_id = await _validate_key(api_key or "")
    if not tenant_id:
        await ws.close(code=4001)
        return
    await ws.accept()
    ws_clients[ws] = tenant_id
    ws_connections.set(len(ws_clients))
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.pop(ws, None)
        ws_connections.set(len(ws_clients))
