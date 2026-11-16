from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .models import AgentOpsEvent

logger = logging.getLogger(__name__)

BREACH_STREAM = "AGENTOPS_BREACHES"
BREACH_SUBJECT = "agentops.slo.breach.*"


async def ensure_breach_stream(nc: Any) -> None:
    """Provision bounded file storage before publishing or consuming breaches."""
    from nats.js.api import DiscardPolicy, StorageType

    await nc.jetstream().add_stream(
        name=BREACH_STREAM,
        subjects=[BREACH_SUBJECT],
        storage=StorageType.FILE,
        max_age=7 * 24 * 60 * 60,
        max_bytes=1024 * 1024 * 1024,
        discard=DiscardPolicy.NEW,
        duplicate_window=120,
    )


async def subscribe_breaches(nc: Any, handler: Any):
    """Resume a durable queue; acknowledge only after enforcement commits."""
    from nats.js.api import AckPolicy, ConsumerConfig

    await ensure_breach_stream(nc)

    async def deliver(msg):
        try:
            event = AgentOpsEvent.model_validate_json(msg.data)
            if not event.event_type.startswith("agentops.slo.breach."):
                raise ValueError("Unexpected event type on enforcement stream")
            agent_id = event.payload.get("agent_id") or event.agent_id
            if agent_id is not None and not isinstance(agent_id, str):
                raise ValueError("Breach agent_id must be a string")
        except (ValueError, TypeError):
            logger.exception("Invalid SLO breach; terminating delivery")
            await msg.term()
            return
        try:
            await handler(msg)
        except Exception:
            logger.exception("SLO enforcement failed; requesting redelivery")
            await msg.nak(delay=1)
        else:
            await msg.ack()

    return await nc.jetstream().subscribe(
        BREACH_SUBJECT,
        stream=BREACH_STREAM,
        durable="cb-lockdown",
        queue="cb-lockdown",
        cb=deliver,
        manual_ack=True,
        config=ConsumerConfig(ack_policy=AckPolicy.EXPLICIT, ack_wait=30, max_ack_pending=1),
    )


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
            if event.event_type.startswith("agentops.slo.breach."):
                await nc.jetstream().publish(
                    event.event_type, data, headers={"Nats-Msg-Id": str(event.event_id)}
                )
            else:
                await nc.publish(event.event_type, data)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2**attempt))
    logger.exception("failed to publish event %s after %d retries", event.event_type, max_retries)
    raise last_exc  # type: ignore


def event_to_dict(event: AgentOpsEvent) -> dict:
    return json.loads(event.model_dump_json())
