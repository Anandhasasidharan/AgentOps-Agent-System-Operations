from __future__ import annotations

import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rpm: int = 60):
        super().__init__(app)
        self.rpm = rpm
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        slug = api_key.split(":", 1)[0] if api_key else "anonymous"

        now = time.time()
        cutoff = now - 60
        self._windows[slug] = [t for t in self._windows[slug] if t > cutoff]

        if len(self._windows[slug]) >= self.rpm:
            return Response(status_code=429, content="Rate limit exceeded")

        self._windows[slug].append(now)
        return await call_next(request)


def add_rate_limiter(app: FastAPI, rpm: int = 60) -> None:
    app.add_middleware(RateLimitMiddleware, rpm=rpm)
