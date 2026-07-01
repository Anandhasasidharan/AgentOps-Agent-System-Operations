from __future__ import annotations

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

CB_URL = os.getenv("CB_URL", "http://localhost:8001")
CHAOS_URL = os.getenv("CHAOS_URL", "http://localhost:8002")
SLO_URL = os.getenv("SLO_URL", "http://localhost:8000")

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = httpx.AsyncClient(timeout=3.0)
    yield
    await _client.aclose()


app = FastAPI(title="AgentOps Dashboard", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _check(url: str) -> dict:
    try:
        r = await _client.get(f"{url}/health")
        r.raise_for_status()
        return {"status": "ok", "data": r.json()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    cb, chaos, slo = await _check(CB_URL), await _check(CHAOS_URL), await _check(SLO_URL)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AgentOps Dashboard</title>
<style>
  body {{ font-family: monospace; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
  .card {{ border: 1px solid #ccc; border-radius: 6px; padding: 16px; margin: 12px 0; }}
  .ok {{ border-left: 4px solid #22c55e; }}
  .err {{ border-left: 4px solid #ef4444; }}
  .status {{ font-weight: bold; }}
  ul {{ margin: 0; padding-left: 20px; }}
  li {{ margin: 4px 0; }}
</style></head>
<body>
<h1>AgentOps Dashboard</h1>
{_card("Circuit Breaker", CB_URL, cb)}
{_card("Chaos Toolkit", CHAOS_URL, chaos)}
{_card("SLO Platform", SLO_URL, slo)}
</body></html>"""


def _card(name: str, url: str, result: dict) -> str:
    ok = result.get("status") == "ok"
    cls = "ok" if ok else "err"
    data = result.get("data", {}) if ok else {}
    items = "".join(f"<li><b>{k}:</b> {v}</li>" for k, v in data.items()) if data else f"<li>{result.get('error', 'unknown')}</li>"
    return f'<div class="card {cls}"><h2>{name}</h2><p class="status">{result["status"]}</p><ul>{items}</ul><p><a href="{url}/docs">API docs</a></p></div>'
