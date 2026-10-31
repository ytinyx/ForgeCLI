"""Non-interactive CLI execution must preserve tool approval boundaries."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from forgecli.__main__ import _run_prompt
from forgecli.agent import Agent, LoopComplete, PermissionRequest, PermissionResponse, StreamText
from forgecli.config import AppConfig, ProviderConfig
from forgecli.permissions import PermissionMode
from forgecli.tools.base import StreamEnd, TextDelta, ToolCallComplete


@pytest.fixture
def cli_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr("forgecli.client.create_client", Mock(return_value=object()))
    monkeypatch.setattr("forgecli.client.resolve_context_window", AsyncMock())
    return AppConfig(providers=[ProviderConfig(
        name="offline", protocol="anthropic", base_url="https://example.invalid", model="offline-test",
    )])


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(PermissionMode))
@pytest.mark.parametrize("output_format", ["text", "stream-json"])
async def test_cli_denies_approval_requests_unless_bypass_selected(cli_config, monkeypatch, capsys, mode, output_format):
    responses = []

    async def request_approval(self, conversation):
        future = asyncio.get_running_loop().create_future()
        yield PermissionRequest("Bash", "private-tool-argument-must-not-be-printed", future)
        responses.append(await future)
        yield StreamText("Finished.")
        yield LoopComplete(1)

    monkeypatch.setattr(Agent, "run", request_approval)
    await _run_prompt(cli_config, mode, None, "offline prompt", output_format)
    captured = capsys.readouterr()
    bypass = mode == PermissionMode.BYPASS
    assert responses == [PermissionResponse.ALLOW if bypass else PermissionResponse.DENY]
    assert "private-tool-argument" not in captured.out + captured.err
    if output_format == "stream-json":
        events = [json.loads(line) for line in captured.out.splitlines()]
        denied = [event for event in events if event["type"] == "permission_denied"]
        assert len(denied) == (0 if bypass else 1)
        if denied:
            assert denied[0]["tool_name"] == "Bash"
            assert "-p mode" in denied[0]["message"]
        assert captured.err == ""
    else:
        assert captured.out == "Finished."
        assert ("Permission denied (Bash)" in captured.err) is not bypass


class OfflineClient:
    """One scripted tool call followed by text; never accesses a model service."""

    def __init__(self, call):
        self.call = call

    async def stream(self, conversation, system="", tools=None):
        if self.call is not None:
            call, self.call = self.call, None
            yield call
        else:
            yield TextDelta("Finished.")
        yield StreamEnd("end_turn", input_tokens=10, output_tokens=10)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(PermissionMode))
async def test_cli_respects_write_permissions_with_real_agent(cli_config, monkeypatch, tmp_path, capsys, mode):
    output = tmp_path / "created.txt"
    client = OfflineClient(ToolCallComplete("write-1", "WriteFile", {
        "file_path": str(output), "content": "created with permission",
    }))
    monkeypatch.setattr("forgecli.client.create_client", lambda provider: client)
    await _run_prompt(cli_config, mode, None, "write a file", "text")
    assert output.exists() is (mode in {PermissionMode.ACCEPT_EDITS, PermissionMode.BYPASS})
    if output.exists():
        assert output.read_text(encoding="utf-8") == "created with permission"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(PermissionMode))
async def test_cli_keeps_preapproved_reads_working(cli_config, monkeypatch, tmp_path, capsys, mode):
    source = tmp_path / "input.txt"
    source.write_text("safe read result", encoding="utf-8")
    client = OfflineClient(ToolCallComplete("read-1", "ReadFile", {"file_path": str(source)}))
    monkeypatch.setattr("forgecli.client.create_client", lambda provider: client)
    await _run_prompt(cli_config, mode, None, "read a file", "stream-json")
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines()]
    results = [event for event in events if event["type"] == "tool_result"]
    assert len(results) == 1
    assert not results[0]["is_error"]
    assert "safe read result" in results[0]["output"]
    assert not any(event["type"] == "permission_denied" for event in events)
