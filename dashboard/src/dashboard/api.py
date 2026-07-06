from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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
    _client = httpx.AsyncClient(timeout=3.0)
    yield
    await _client.aclose()


app = FastAPI(title="AgentOps Dashboard", version="0.1.0", lifespan=lifespan)

add_metrics_route(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
async def proxy_events():
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    try:
        r = await _client.get(f"{GATEWAY_URL}/api/v1/events", headers=headers)
        return r.json()
    except Exception:
        return []


async def _check(url: str, name: str) -> dict:
    t0 = time.time()
    try:
        r = await _client.get(f"{url}/health")
        r.raise_for_status()
        upstream_health.labels(service=name).set(1)
        health_check_duration_seconds.labels(service=name).observe(time.time() - t0)
        return {"status": "ok", "data": r.json()}
    except Exception as e:
        upstream_health.labels(service=name).set(0)
        health_check_duration_seconds.labels(service=name).observe(time.time() - t0)
        return {"status": "error", "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    cb = await _check(CB_URL, "circuit-breaker")
    chaos = await _check(CHAOS_URL, "chaos-toolkit")
    slo = await _check(SLO_URL, "slo-platform")
    ws_url = GATEWAY_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    if API_KEY:
        ws_url += f"?api_key={API_KEY}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AgentOps Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: ui-monospace, 'Cascadia Code', 'SF Mono', monospace; background: #0f172a; color: #e2e8f0; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 1.5rem; border-bottom: 1px solid #334155; padding-bottom: 8px; margin-bottom: 16px; color: #38bdf8; }}
  h2 {{ font-size: 1rem; margin-bottom: 8px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .card {{ border: 1px solid #334155; border-radius: 8px; padding: 14px; background: #1e293b; }}
  .ok {{ border-left: 4px solid #22c55e; }}
  .err {{ border-left: 4px solid #ef4444; }}
  .status {{ font-weight: bold; font-size: 0.9rem; }}
  .status.ok {{ color: #22c55e; }}
  .status.err {{ color: #ef4444; }}
  .health-data {{ font-size: 0.8rem; color: #94a3b8; margin: 6px 0; }}
  .health-data li {{ display: inline-block; margin-right: 12px; }}
  a {{ color: #38bdf8; }}
  #events {{ border: 1px solid #334155; border-radius: 8px; background: #1e293b; }}
  #events h2 {{ padding: 14px; border-bottom: 1px solid #334155; }}
  #event-list {{ max-height: 600px; overflow-y: auto; padding: 8px; }}
  .event {{ padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 0.8rem; border-left: 3px solid #475569; }}
  .event .time {{ color: #64748b; margin-right: 8px; }}
  .event .type {{ font-weight: bold; color: #38bdf8; }}
  .event.intercept {{ border-left-color: #22c55e; }}
  .event.intercept.block {{ border-left-color: #ef4444; }}
  .event.incident {{ border-left-color: #f97316; }}
  .event.kill {{ border-left-color: #ef4444; }}
  .event.breach {{ border-left-color: #eab308; }}
  .event.experiment {{ border-left-color: #a855f7; }}
  .event .payload {{ color: #94a3b8; font-size: 0.75rem; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 600px; }}
  .conn-badge {{ display: inline-block; font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }}
  .conn-badge.on {{ background: #166534; color: #22c55e; }}
  .conn-badge.off {{ background: #7f1d1d; color: #ef4444; }}
  .health-summary {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
</style></head>
<body>
<div class="container">
  <h1>AgentOps <span style="color:#94a3b8;font-size:0.9rem">— real-time agent operations</span></h1>
  <div class="cards">
    {_card("Circuit Breaker", CB_URL, cb)}
    {_card("Chaos Toolkit", CHAOS_URL, chaos)}
    {_card("SLO Platform", SLO_URL, slo)}
  </div>

  <div id="events">
    <h2>Live Events <span id="conn-badge" class="conn-badge off">disconnected</span></h2>
    <div id="event-list"><p style="color:#64748b;padding:12px;">connecting...</p></div>
  </div>
</div>

<script>
(function() {{
  const wsUrl = "{ws_url}";
  const list = document.getElementById('event-list');
  const badge = document.getElementById('conn-badge');
  let ws = null;
  let pollInterval = null;

  function addEvent(data) {{
    const div = document.createElement('div');
    const type = data.event_type || '';
    const ts = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '';
    const payload = data.payload || {{}};
    const agent = payload.agent_id || data.agent_id || '?';

    let cls = 'event';
    if (type.includes('intercept')) cls += ' intercept' + (payload.verdict === 'block' ? ' block' : '');
    else if (type.includes('incident')) cls += ' incident';
    else if (type.includes('kill')) cls += ' kill';
    else if (type.includes('breach')) cls += ' breach';
    else if (type.includes('experiment')) cls += ' experiment';

    let summary = type.split('.').slice(2).join('.') || type;
    div.className = cls;
    div.innerHTML = '<span class="time">' + ts + '</span>'
      + '<span class="type">' + summary + '</span> '
      + '<span style="color:#94a3b8">' + agent + '</span>'
      + '<div class="payload">' + JSON.stringify(payload).slice(0, 200) + '</div>';
    list.insertBefore(div, list.firstChild);
    while (list.children.length > 200) list.removeChild(list.lastChild);
  }}

  function connect() {{
    try {{
      ws = new WebSocket(wsUrl);
      ws.onopen = function() {{
        badge.textContent = 'connected';
        badge.className = 'conn-badge on';
        list.innerHTML = '';
        if (pollInterval) {{ clearInterval(pollInterval); pollInterval = null; }}
      }};
      ws.onmessage = function(e) {{
        try {{ addEvent(JSON.parse(e.data)); }} catch(ex) {{}}
      }};
      ws.onclose = function() {{
        badge.textContent = 'reconnecting...';
        badge.className = 'conn-badge off';
        if (!pollInterval) startPolling();
        setTimeout(connect, 3000);
      }};
    }} catch(e) {{
      badge.textContent = 'ws failed';
      startPolling();
    }}
  }}

  function startPolling() {{
    pollInterval = setInterval(function() {{
      fetch('/events').then(r => r.json()).then(events => {{
        if (list.children.length === 0 || list.querySelector('p')) {{
          list.innerHTML = '';
          events.slice(-50).forEach(addEvent);
        }}
      }}).catch(function() {{}});
    }}, 3000);
  }}

  connect();
}})();
</script>
</body></html>"""


def _card(name: str, url: str, result: dict) -> str:
    ok = result.get("status") == "ok"
    cls = "ok" if ok else "err"
    data = result.get("data", {}) if ok else {}
    items = (
        "".join(f"<li><b>{k}:</b> {v}</li>" for k, v in data.items())
        if data
        else f"<li>{result.get('error', 'unknown')}</li>"
    )
    return (
        f'<div class="card {cls}"><h2>{name}</h2>'
        f'<p class="status {cls}">{result["status"]}</p>'
        f'<ul class="health-data">{items}</ul>'
        f'<p><a href="{url}/docs">API docs</a></p></div>'
    )
