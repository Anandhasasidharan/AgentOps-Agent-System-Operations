from __future__ import annotations

import json
import logging
from typing import Any

from .models import AgentOpsEvent

logger = logging.getLogger(__name__)


async def create_nats_client(url: str | None = None) -> Any | None:
    if not url:
        return None
    try:
        import nats

        nc = await nats.connect(url, max_reconnect_attempts=2)
        logger.info("connected to NATS at %s", url)
        return nc
    except Exception:
        logger.warning("NATS unavailable at %s, events disabled", url)
        return None


async def publish_event(nc: Any | None, event: AgentOpsEvent):
    if nc is None:
        return
    try:
        data = event.model_dump_json().encode()
        await nc.publish(event.event_type, data)
    except Exception:
        logger.exception("failed to publish event %s", event.event_type)


def event_to_dict(event: AgentOpsEvent) -> dict:
    return json.loads(event.model_dump_json())
