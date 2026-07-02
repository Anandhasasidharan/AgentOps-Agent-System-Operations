from agentops_events import AgentOpsEvent, make_event
from agentops_events.models import TOPIC_CB_INTERCEPT

import uuid


def test_make_event():
    tid = uuid.uuid4()
    event = make_event("test", TOPIC_CB_INTERCEPT.format(verdict="allow"), tid, {"key": "val"}, "agent-1")
    assert event.source == "test"
    assert event.event_type == "agentops.cb.intercept.allow"
    assert event.tenant_id == tid
    assert event.agent_id == "agent-1"
    assert event.payload == {"key": "val"}


def test_event_serialization():
    tid = uuid.uuid4()
    event = make_event("test", "agentops.test.event", tid, {"n": 42})
    d = event.model_dump()
    assert d["source"] == "test"
    assert d["event_type"] == "agentops.test.event"
    assert d["tenant_id"] == tid
    assert d["payload"]["n"] == 42


def test_all_topics():
    from agentops_events.models import ALL_TOPICS
    assert "agentops.cb.intercept.*" in ALL_TOPICS
    assert "agentops.slo.breach.*" in ALL_TOPICS
    assert len(ALL_TOPICS) == 6
