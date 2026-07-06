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
    mock_nc.publish = AsyncMock(
        side_effect=[Exception("fail1"), Exception("fail2"), None]
    )
    event = make_event("test", "agentops.test.event", uuid.uuid4(), {"k": "v"})
    await publish_event(mock_nc, event, max_retries=2)
    assert mock_nc.publish.await_count == 3
