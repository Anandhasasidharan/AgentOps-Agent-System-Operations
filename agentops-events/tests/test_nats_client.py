from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import agentops_events.nats_client as nc_module
import pytest
from agentops_events import create_nats_client, make_event, publish_event


@pytest.mark.asyncio
async def test_create_nats_client_none():
    nc = await create_nats_client(None)
    assert nc is None


@pytest.mark.asyncio
async def test_create_nats_client_empty():
    nc = await create_nats_client("")
    assert nc is None


@pytest.mark.asyncio
async def test_create_nats_client_success():
    mock_nc = AsyncMock()
    with patch.object(nc_module, "HAS_NATS", True):
        with patch.object(nc_module, "_nats", MagicMock()) as mock_nats:
            mock_nats.connect = AsyncMock(return_value=mock_nc)
            nc = await create_nats_client("nats://localhost:4222")
    assert nc is not None
    mock_nats.connect.assert_called_once()


@pytest.mark.asyncio
async def test_create_nats_client_failure():
    with patch.object(nc_module, "HAS_NATS", True):
        with patch.object(nc_module, "_nats", MagicMock()) as mock_nats:
            mock_nats.connect = AsyncMock(side_effect=Exception("connection refused"))
            nc = await create_nats_client("nats://localhost:4222")
    assert nc is None


@pytest.mark.asyncio
async def test_publish_event_no_nc():
    event = make_event("test", "agentops.test.event", uuid.uuid4(), {"k": "v"})
    await publish_event(None, event)


@pytest.mark.asyncio
async def test_publish_event_success():
    mock_nc = AsyncMock()
    event = make_event("test", "agentops.test.event", uuid.uuid4(), {"k": "v"})
    await publish_event(mock_nc, event)
    assert mock_nc.publish.called


@pytest.mark.asyncio
async def test_publish_event_failure():
    mock_nc = AsyncMock()
    mock_nc.publish = AsyncMock(side_effect=Exception("publish failed"))
    event = make_event("test", "agentops.test.event", uuid.uuid4(), {"k": "v"})
    with pytest.raises(Exception, match="publish failed"):
        await publish_event(mock_nc, event)


@pytest.mark.asyncio
async def test_publish_event_retries():
    mock_nc = AsyncMock()
    mock_nc.publish = AsyncMock(side_effect=[Exception("fail1"), Exception("fail2"), None])
    event = make_event("test", "agentops.test.event", uuid.uuid4(), {"k": "v"})
    await publish_event(mock_nc, event, max_retries=2)
    assert mock_nc.publish.await_count == 3


@pytest.mark.asyncio
async def test_breach_publish_waits_for_storage_ack_and_reuses_event_id():
    nc = MagicMock()
    js = nc.jetstream.return_value
    js.publish = AsyncMock(side_effect=[RuntimeError("ack lost"), object()])
    event = make_event("slo", "agentops.slo.breach.7d", uuid.uuid4(), {})
    await publish_event(nc, event, base_delay=0)
    assert js.publish.await_count == 2
    for call in js.publish.call_args_list:
        assert call.kwargs["headers"] == {"Nats-Msg-Id": str(event.event_id)}
    nc.publish.assert_not_called()


@pytest.mark.asyncio
async def test_durable_delivery_ack_retry_and_invalid_message():
    from agentops_events import subscribe_breaches

    nc = MagicMock()
    js = nc.jetstream.return_value
    js.add_stream = AsyncMock()
    js.subscribe = AsyncMock()
    handler = AsyncMock()
    await subscribe_breaches(nc, handler)
    config = js.subscribe.call_args.kwargs
    assert config["manual_ack"] is True
    assert config["durable"] == "cb-lockdown"
    deliver = config["cb"]

    message = AsyncMock()
    message.data = (
        make_event("slo", "agentops.slo.breach.7d", uuid.uuid4(), {}).model_dump_json().encode()
    )
    await deliver(message)
    handler.assert_awaited_once_with(message)
    message.ack.assert_awaited_once()
    message.nak.assert_not_awaited()

    handler.side_effect = RuntimeError("database offline")
    message.reset_mock()
    await deliver(message)
    message.ack.assert_not_awaited()
    message.nak.assert_awaited_once_with(delay=1)

    handler.side_effect = None
    message.data = b"invalid JSON"
    message.reset_mock()
    await deliver(message)
    message.term.assert_awaited_once()
    message.ack.assert_not_awaited()
    message.nak.assert_not_awaited()
