from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

TOPIC_CB_INTERCEPT = "agentops.cb.intercept.{verdict}"
TOPIC_CB_INCIDENT = "agentops.cb.incident.{severity}"
TOPIC_CB_KILL = "agentops.cb.kill.{action}"
TOPIC_CHAOS_EXPERIMENT = "agentops.chaos.experiment.{status}"
TOPIC_SLO_BREACH = "agentops.slo.breach.{window}"
TOPIC_SLO_ALERT = "agentops.slo.alert.{severity}"

ALL_TOPICS = [
    "agentops.cb.intercept.*",
    "agentops.cb.incident.*",
    "agentops.cb.kill.*",
    "agentops.chaos.experiment.*",
    "agentops.slo.breach.*",
    "agentops.slo.alert.*",
]


class AgentOpsEvent(BaseModel):
    event_id: uuid.UUID
    source: str
    event_type: str
    tenant_id: uuid.UUID
    agent_id: str | None = None
    timestamp: datetime
    payload: dict


def make_event(
    source: str,
    event_type: str,
    tenant_id: uuid.UUID,
    payload: dict,
    agent_id: str | None = None,
) -> AgentOpsEvent:
    return AgentOpsEvent(
        event_id=uuid.uuid4(),
        source=source,
        event_type=event_type,
        tenant_id=tenant_id,
        agent_id=agent_id,
        timestamp=datetime.now(tz=timezone.utc),
        payload=payload,
    )
