"""Configured MCP headers must never be forwarded to a redirect destination."""

from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import pytest

from forgecli.config import MCPServerConfig
from forgecli.mcp.client import MCPClient


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
async def test_http_mcp_rejects_redirects_without_forwarding_custom_credentials(monkeypatch, status_code):
    requested_urls = []

    def respond(request):
        requested_urls.append(str(request.url))
        if request.url.host == "configured.example.invalid":
            assert request.headers["X-MCP-API-Key"] == "test-only-key"
            return httpx.Response(status_code, headers={
                "Location": "https://untrusted.example.invalid/collect",
            })
        return httpx.Response(500)

    async_client = httpx.AsyncClient

    def isolated_client(**kwargs):
        return async_client(**kwargs, transport=httpx.MockTransport(respond), trust_env=False)

    @asynccontextmanager
    async def probe_transport(url, *, http_client):
        # Exercise the configured real HTTPX client as the MCP transport does,
        # while avoiding session-handshake tasks unrelated to redirect handling.
        response = await http_client.post(url, json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
        response.raise_for_status()
        yield None, None, None

    monkeypatch.setattr("forgecli.mcp.client.httpx.AsyncClient", isolated_client)
    monkeypatch.setattr("forgecli.mcp.client.streamable_http_client", probe_transport)
    client = MCPClient(MCPServerConfig(
        name="redirect-test",
        url="https://configured.example.invalid/mcp",
        headers={"X-MCP-API-Key": "test-only-key"},
    ))
    async with AsyncExitStack() as stack:
        client._stack = stack
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client._connect_http()
        assert requested_urls == ["https://configured.example.invalid/mcp"]
        assert exc.value.response.status_code == status_code
