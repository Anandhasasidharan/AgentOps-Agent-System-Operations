from unittest.mock import patch

import httpx
import pytest

from agentops_core.telemetry import emit_tool_call_span


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401, 503])
async def test_telemetry_uses_full_key_and_reports_rejection(status, caplog):
    key = "acme:secret-token"
    seen = []

    def receive(request):
        seen.append(request.headers["X-API-Key"])
        return httpx.Response(status)

    client = httpx.AsyncClient(transport=httpx.MockTransport(receive))
    with patch("agentops_core.telemetry.httpx.AsyncClient", return_value=client):
        await emit_tool_call_span("http://slo/v1/traces", key, "agent", "read_file", False)
    assert seen == [key]
    failures = [
        r for r in caplog.records if getattr(r, "event", "") == "agentops.telemetry_export_failed"
    ]
    assert len(failures) == (0 if status == 200 else 1)
    assert key not in caplog.text


@pytest.mark.asyncio
async def test_telemetry_transport_failure_does_not_expose_credentials(caplog):
    def receive(request):
        raise httpx.ConnectError("secret-token", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(receive))
    with patch("agentops_core.telemetry.httpx.AsyncClient", return_value=client):
        await emit_tool_call_span(
            "http://slo/v1/traces", "acme:secret-token", "agent", "read", False
        )
    assert "agentops.telemetry_export_failed" in [getattr(r, "event", "") for r in caplog.records]
    assert "secret-token" not in caplog.text
