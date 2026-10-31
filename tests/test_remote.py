"""Remote mode must authenticate before exposing the local agent."""

import asyncio
from contextlib import asynccontextmanager
from html.parser import HTMLParser
import json
import re
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import websockets
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.http11 import Request

from forgecli.permissions import PermissionMode
from forgecli.remote import RemoteServer
from forgecli.web_content import INDEX_HTML


def test_remote_rejects_public_bind_addresses():
    assert RemoteServer([]).addr == "127.0.0.1"
    for addr in ("0.0.0.0", "::", "192.168.1.1", "example.com"):
        with pytest.raises(ValueError, match="loopback"):
            RemoteServer([], addr=addr)


@pytest.mark.parametrize("host", [None, "evil.example:18888", "127.0.0.1:9999", "localhost.evil:18888"])
def test_http_rejects_rebinding_hosts(host):
    headers = websockets.Headers()
    if host is not None:
        headers["Host"] = host
    response = RemoteServer([])._process_http_request(None, Request("/", headers))
    assert response.status_code == 403


def test_http_rejects_duplicate_host_headers():
    headers = websockets.Headers([("Host", "127.0.0.1:18888"), ("Host", "evil.example")])
    assert RemoteServer([])._process_http_request(None, Request("/", headers)).status_code == 403


def test_page_has_security_headers_and_does_not_disclose_token():
    remote = RemoteServer([])
    response = remote._process_http_request(None, Request("/", websockets.Headers({"Host": "127.0.0.1:18888"})))
    assert response.status_code == 200
    assert remote._auth_token.encode() not in response.body
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert f"script-src 'nonce-{remote._script_nonce}'" in response.headers["Content-Security-Policy"]

    class PageParser(HTMLParser):
        scripts = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            assert not any(name.startswith("on") for name in attributes)
            if tag == "script":
                assert "src" not in attributes
                self.scripts.append(attributes)

    parser = PageParser()
    parser.feed(response.body.decode())
    assert parser.scripts == [{"nonce": remote._script_nonce}]


@pytest.mark.skipif(shutil.which("node") is None, reason="JavaScript rendering check requires Node.js")
def test_browser_script_escapes_model_html_and_attribute_values():
    script = re.search(r"<script>(.*?)</script>", INDEX_HTML, re.DOTALL).group(1)
    harness = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const node = { addEventListener() {}, focus() {} };
const sandbox = {
  document: { getElementById() { return node; } },
  location: { hash: '', pathname: '/' },
  sessionStorage: { getItem() { return null; } },
  URLSearchParams,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(0, 'utf8'), sandbox);
sandbox.payload = '<img src=x onerror="alert(1)">';
assert.equal(vm.runInContext('renderMarkdown(payload)', sandbox), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
sandbox.payload = '```html\n<script>alert(1)</script>\n```';
assert.equal(vm.runInContext('renderMarkdown(payload)', sandbox), '<pre><code>&lt;script&gt;alert(1)&lt;/script&gt;\n</code></pre>');
sandbox.payload = '\" autofocus onfocus=\"alert(1)\"\'';
assert.equal(vm.runInContext('escapeHtml(payload)', sandbox), '&quot; autofocus onfocus=&quot;alert(1)&quot;&#39;');
"""
    result = subprocess.run([shutil.which("node"), "-e", harness], input=script, text=True, encoding="utf-8", capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


@asynccontextmanager
async def running_remote():
    remote = RemoteServer([])
    async with websockets.serve(remote._ws_handler, remote.addr, 0, process_request=remote._process_http_request) as server:
        remote.port = server.sockets[0].getsockname()[1]
        yield remote, f"ws://127.0.0.1:{remote.port}/ws", f"http://127.0.0.1:{remote.port}"


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", [None, "null", "https://evil.example", "http://127.0.0.1:1"])
async def test_websocket_rejects_missing_and_cross_site_origins(origin):
    async with running_remote() as (_, url, _):
        with pytest.raises(InvalidStatus) as exc:
            async with websockets.connect(url, origin=origin, proxy=None):
                pytest.fail("Cross-site socket was accepted")
        assert exc.value.response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("auth", [None, [], {"type": "ping"}, {"type": "auth", "token": "wrong"}, {"type": "auth", "token": "错误"}, {"type": "auth", "token": "\ud800"}])
async def test_websocket_rejects_invalid_authentication_without_broadcasting(auth):
    async with running_remote() as (remote, url, origin):
        async with websockets.connect(url, origin=origin, proxy=None) as socket:
            await socket.send(json.dumps(auth))
            with pytest.raises(ConnectionClosedError) as exc:
                await socket.recv()
            assert exc.value.rcvd.code == 1008
            assert not remote._connections


@pytest.mark.asyncio
async def test_authenticated_socket_receives_events_and_unauthenticated_socket_does_not():
    async with running_remote() as (remote, url, origin):
        async with websockets.connect(url, origin=origin, proxy=None) as pending:
            async with websockets.connect(url, origin=origin, proxy=None) as socket:
                await socket.send(json.dumps({"type": "auth", "token": remote._auth_token}))
                assert json.loads(await socket.recv())["type"] == "connected"
                assert json.loads(await socket.recv())["type"] == "commands"
                assert len(remote._connections) == 1
                for invalid in ([], {"type": "user_message", "data": None}, {"type": "user_message", "data": {"content": []}}):
                    await socket.send(json.dumps(invalid))
                await socket.send(json.dumps({"type": "ping", "data": {}}))
                assert json.loads(await socket.recv())["type"] == "pong"
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(pending.recv(), timeout=0.05)


@pytest.mark.parametrize("flags, expected", [([], PermissionMode.ACCEPT_EDITS), (["--mode", "plan"], PermissionMode.PLAN)])
def test_cli_passes_configured_permission_mode_to_remote(tmp_path, monkeypatch, flags, expected):
    from forgecli import __main__ as cli

    received = {}

    class FakeRemote:
        def __init__(self, **kwargs):
            received.update(kwargs)

        async def run(self):
            pass

    config = SimpleNamespace(permission_mode="acceptEdits", providers=[], mcp_servers=[], raw_hooks=[])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr("forgecli.remote.RemoteServer", FakeRemote)
    monkeypatch.setattr("sys.argv", ["forgecli", "--remote", *flags])
    cli.main()
    assert received["permission_mode"] is expected


def test_remote_initializes_checker_with_selected_permission_mode(monkeypatch, tmp_path):
    class StopInitialization(Exception):
        pass

    checker = Mock(side_effect=StopInitialization)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("forgecli.remote.PermissionChecker", checker)
    remote = RemoteServer([SimpleNamespace()], permission_mode=PermissionMode.PLAN)
    with pytest.raises(StopInitialization):
        remote._init_agent()
    assert checker.call_args.kwargs["mode"] is PermissionMode.PLAN
