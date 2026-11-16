from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from websockets.exceptions import WebSocketException

from dashboard.metrics import (
    add_metrics_route,
    health_check_duration_seconds,
    upstream_health,
)

CB_URL = os.getenv("CB_URL", "http://localhost:8001")
CHAOS_URL = os.getenv("CHAOS_URL", "http://localhost:8002")
SLO_URL = os.getenv("SLO_URL", "http://localhost:8000")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8004")
API_KEY = os.getenv("API_KEY", "")

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = httpx.AsyncClient(timeout=5.0)
    yield
    await _client.aclose()


app = FastAPI(title="AgentOps Dashboard", version="0.1.0", lifespan=lifespan)

add_metrics_route(app)


def session_token():
    return hmac.new(API_KEY.encode(), b"agentops-dashboard-session-v1", hashlib.sha256).hexdigest()


def authorized(headers, cookies):
    if not API_KEY:
        return False
    supplied = headers.get("X-API-Key", "")
    try:
        scheme, value = headers.get("Authorization", "").split(" ", 1)
        if scheme.lower() == "basic":
            _, password = base64.b64decode(value, validate=True).decode().split(":", 1)
            supplied = supplied or password
    except (ValueError, UnicodeError):
        pass
    return secrets.compare_digest(supplied.encode(), API_KEY.encode()) or secrets.compare_digest(
        cookies.get("agentops_session", ""), session_token()
    )


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if request.url.path in ("/health", "/metrics"):
        return await call_next(request)
    if not authorized(request.headers, request.cookies):
        return HTMLResponse(
            "Authentication required. Use your tenant API key as the password.",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="AgentOps"'},
        )
    origin = request.headers.get("origin")
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and origin
        and origin != str(request.base_url).rstrip("/")
    ):
        return JSONResponse({"detail": "Cross-origin operation rejected"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.path == "/":
        response.set_cookie(
            "agentops_session",
            session_token(),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            max_age=43200,
        )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
async def proxy_events():
    try:
        r = await _client.get(f"{GATEWAY_URL}/api/v1/events", headers={"X-API-Key": API_KEY})
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError, AttributeError):
        return JSONResponse({"detail": "Event gateway unavailable"}, status_code=502)


async def _check(url: str, name: str) -> dict:
    t0 = time.time()
    try:
        r = await _client.get(f"{url}/health", timeout=3.0)
        r.raise_for_status()
        upstream_health.labels(service=name).set(1)
        health_check_duration_seconds.labels(service=name).observe(time.time() - t0)
        return {"status": "ok", "data": r.json()}
    except Exception as e:
        upstream_health.labels(service=name).set(0)
        health_check_duration_seconds.labels(service=name).observe(time.time() - t0)
        return {"status": "error", "error": str(e)}


@app.get("/api/health")
async def aggregate_health():
    results = {}
    for name, url in (
        ("circuit-breaker", CB_URL),
        ("chaos-toolkit", CHAOS_URL),
        ("slo-platform", SLO_URL),
        ("gateway", GATEWAY_URL),
    ):
        results[name] = await _check(url, name)
    gateway = results["gateway"].get("data", {})
    results["nats"] = {"status": "ok" if gateway.get("nats_connected") else "error"}
    return {
        "status": "ok" if all(r["status"] == "ok" for r in results.values()) else "degraded",
        "services": results,
    }


STATIC = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

SERVICES = {
    "breaker": lambda: CB_URL,
    "slo": lambda: SLO_URL,
    "chaos": lambda: CHAOS_URL,
    "gateway": lambda: GATEWAY_URL,
}
ROUTES = {
    "breaker": {
        "GET": r"api/v1/(policies(?:/[^/]+)?|tool-calls|incidents(?:/[^/]+/rollbacks)?|agents/[^/]+/status|kill-switch/[^/]+|predict/[^/]+|graph/(status|anomalies))",
        "POST": r"(v1/intercept|api/v1/(policies|kill-switch/[^/]+/(activate|release)|incidents/[^/]+/(resolve|rollback)))",
        "DELETE": r"api/v1/policies/[^/]+",
    },
    "slo": {
        "GET": r"api/v1/(tenants/me|agents|slis|slos|status|alerts|compliance/(owasp|eu-ai-act))",
        "POST": r"(v1/traces|api/v1/(agents|slis|slos|alerts/[^/]+/resolve))",
    },
    "chaos": {
        "GET": r"api/v1/(scenarios(?:/[^/]+)?|experiments(?:/[^/]+)?|resilience-score|reports(?:/[^/]+/(junit|github-summary))?)",
        "POST": r"api/v1/(scenarios(?:/(seed|propose|refine))?|experiments(?:/batch)?|reports)",
    },
    "gateway": {"GET": r"api/v1/events"},
}


@app.api_route("/api/services/{service}/{path:path}", methods=["GET", "POST", "DELETE"])
async def service_proxy(service: str, path: str, request: Request):
    pattern = ROUTES.get(service, {}).get(request.method)
    if not pattern or not re.fullmatch(pattern, path) or ".." in path:
        return JSONResponse({"detail": "Unsupported service operation"}, status_code=404)
    body = await request.body()
    if len(body) > 1024 * 1024:
        return JSONResponse({"detail": "Request exceeds 1 MiB"}, status_code=413)
    try:
        upstream = await _client.request(
            request.method,
            SERVICES[service]().rstrip("/") + "/" + path,
            params=request.query_params,
            content=body,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=150.0 if service == "chaos" and request.method == "POST" else 10.0,
        )
        return Response(
            upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )
    except httpx.HTTPError:
        return JSONResponse(
            {"detail": f"{service} service unavailable; operation was not confirmed"},
            status_code=502,
        )


SNAPSHOT = {
    "agents": ("slo", "api/v1/agents"),
    "slis": ("slo", "api/v1/slis"),
    "slos": ("slo", "api/v1/slos"),
    "status": ("slo", "api/v1/status"),
    "alerts": ("slo", "api/v1/alerts"),
    "tenant": ("slo", "api/v1/tenants/me"),
    "policies": ("breaker", "api/v1/policies"),
    "calls": ("breaker", "api/v1/tool-calls?limit=100"),
    "incidents": ("breaker", "api/v1/incidents"),
    "graph": ("breaker", "api/v1/graph/status"),
    "anomalies": ("breaker", "api/v1/graph/anomalies"),
    "scenarios": ("chaos", "api/v1/scenarios"),
    "experiments": ("chaos", "api/v1/experiments"),
    "resilience": ("chaos", "api/v1/resilience-score"),
    "reports": ("chaos", "api/v1/reports"),
    "events": ("gateway", "api/v1/events"),
}


@app.get("/api/snapshot")
async def snapshot():
    async def fetch(name, service, path):
        try:
            response = await _client.get(
                SERVICES[service]().rstrip("/") + "/" + path, headers={"X-API-Key": API_KEY}
            )
            response.raise_for_status()
            return name, response.json(), None
        except (httpx.HTTPError, ValueError):
            return name, None, f"Unable to load {name} from {service}"

    results = await asyncio.gather(*(fetch(name, *route) for name, route in SNAPSHOT.items()))
    return {
        "data": {name: value for name, value, _ in results},
        "errors": [error for _, _, error in results if error],
    }


@app.websocket("/ws")
async def event_socket(ws: WebSocket):
    origin = ws.headers.get("origin")
    if not authorized(ws.headers, ws.cookies) or (
        origin and origin.split("://", 1)[-1] != ws.headers.get("host")
    ):
        await ws.close(code=4001)
        return
    await ws.accept()
    url = GATEWAY_URL.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    try:
        async with websockets.connect(
            url + "/ws?" + urlencode({"api_key": API_KEY}), open_timeout=5
        ) as upstream:

            async def send():
                async for message in upstream:
                    await ws.send_text(message)

            async def receive():
                while True:
                    await upstream.send(await ws.receive_text())

            tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (OSError, TimeoutError, WebSocketDisconnect, WebSocketException):
        try:
            await ws.close(code=1013)
        except RuntimeError:
            pass


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((STATIC / "index.html").read_text())
