from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .models import AgentOpsEvent

logger = logging.getLogger(__name__)

try:
    import nats as _nats

    HAS_NATS = True
except ImportError:
    _nats = None  # type: ignore
    HAS_NATS = False


async def create_nats_client(url: str | None = None) -> Any | None:
    if not url or not HAS_NATS:
        return None
    try:
        nc = await _nats.connect(url, max_reconnect_attempts=2)
        logger.info("connected to NATS at %s", url)
        return nc
    except Exception:
        logger.warning("NATS unavailable at %s, events disabled", url)
        return None


async def publish_event(
    nc: Any | None,
    event: AgentOpsEvent,
    max_retries: int = 2,
    base_delay: float = 0.1,
):
    if nc is None:
        return
    data = event.model_dump_json().encode()
    last_exc: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            await nc.publish(event.event_type, data)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2**attempt))
    logger.exception(
        "failed to publish event %s after %d retries", event.event_type, max_retries
    )
    raise last_exc  # type: ignore


def event_to_dict(event: AgentOpsEvent) -> dict:
    return json.loads(event.model_dump_json())
