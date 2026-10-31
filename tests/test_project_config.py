"""Project configuration, instructions, environment overrides and protected paths."""

import os
from pathlib import Path

import pytest

from forgecli.config import load_config
from forgecli.mcp.loading_strategy import McpLoadingMode, decide_mode
from forgecli.memory.auto_memory import get_auto_mem_path, get_user_auto_mem_path
from forgecli.memory.instructions import load_instructions
from forgecli.permissions.sandbox import PathSandbox


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _provider(name):
    return (
        "providers:\n"
        f"  - name: {name}\n"
        "    protocol: openai\n"
        "    base_url: https://example.invalid/v1\n"
        "    model: offline-test\n"
    )


@pytest.fixture
def config_paths(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(project)
    return home, project


def test_config_priority_user_then_project_then_local(config_paths):
    home, project = config_paths
    _write(home / ".forgecli/config.yaml", _provider("user"))
    assert load_config().providers[0].name == "user"
    _write(project / ".forgecli/config.yaml", _provider("project"))
    assert load_config().providers[0].name == "project"
    _write(project / ".forgecli/config.local.yaml", _provider("local"))
    assert load_config().providers[0].name == "local"


def test_config_layers_merge_mcp_servers_by_name(config_paths):
    home, project = config_paths
    _write(
        home / ".forgecli/config.yaml",
        _provider("user")
        + "mcp_servers:\n"
        + "  - name: shared\n    command: user-server\n"
        + "  - name: user-only\n    command: user-only-server\n",
    )
    _write(
        project / ".forgecli/config.yaml",
        _provider("project")
        + "mcp_servers:\n"
        + "  - name: shared\n    command: project-server\n"
        + "  - name: project-only\n    command: project-only-server\n",
    )
    servers = load_config().mcp_servers
    assert [(server.name, server.command) for server in servers] == [
        ("shared", "project-server"),
        ("user-only", "user-only-server"),
        ("project-only", "project-only-server"),
    ]


def test_explicit_config_path_does_not_load_ambient_layers(config_paths):
    home, project = config_paths
    _write(home / ".forgecli/config.yaml", "invalid: [yaml")
    _write(project / ".forgecli/config.yaml", "invalid: [yaml")
    explicit = project / "custom.yaml"
    _write(explicit, _provider("explicit"))
    assert load_config(explicit).providers[0].name == "explicit"


def test_instructions_load_user_project_directory_chain_and_local_in_order(config_paths):
    home, project = config_paths
    (project / ".git").mkdir()
    work_dir = project / "src"
    work_dir.mkdir()
    sources = [
        (home / ".forgecli/FORGECLI.md", "user-forge-instructions"),
        (home / ".forgecli/AGENTS.md", "user-agent-instructions"),
        (project / "FORGECLI.md", "project-forge-instructions"),
        (project / "AGENTS.md", "project-agent-instructions"),
        (project / ".forgecli/FORGECLI.md", "project-private-instructions"),
        (work_dir / "FORGECLI.md", "directory-forge-instructions"),
        (work_dir / "AGENTS.md", "directory-agent-instructions"),
        (work_dir / ".forgecli/FORGECLI.md", "directory-private-instructions"),
        (work_dir / "FORGECLI.local.md", "local-instructions"),
    ]
    for path, content in sources:
        _write(path, content)
    result = load_instructions(str(work_dir))
    positions = [result.index("\n\n" + content) for _, content in sources]
    assert positions == sorted(positions)
    for _, content in sources:
        assert result.count("\n\n" + content) == 1


@pytest.mark.parametrize("mode", list(McpLoadingMode))
def test_mcp_environment_override(monkeypatch, mode):
    monkeypatch.setenv("FORGECLI_MCP_LOADING", f" {mode.value.upper()} ")
    assert decide_mode("", 100000, 0) is mode


@pytest.mark.parametrize("override", [None, "", "invalid"])
def test_mcp_environment_without_valid_override_uses_automatic_selection(monkeypatch, override):
    if override is None:
        monkeypatch.delenv("FORGECLI_MCP_LOADING", raising=False)
    else:
        monkeypatch.setenv("FORGECLI_MCP_LOADING", override)
    assert decide_mode("", 100000, 0) is McpLoadingMode.EAGER
    assert decide_mode("", 100000, 100000) is McpLoadingMode.NATIVE
    assert decide_mode("https://example.invalid", 100000, 100000) is McpLoadingMode.DISPATCH


def test_memory_environment_override_and_empty_value_restore_project_path(config_paths, monkeypatch):
    home, project = config_paths
    override = str(project / "remote-memory")
    monkeypatch.setenv("FORGECLI_REMOTE_MEMORY_DIR", override + os.sep)
    assert get_auto_mem_path(str(project)) == override + os.sep
    assert get_user_auto_mem_path() == str(home / ".forgecli/memory") + os.sep
    monkeypatch.setenv("FORGECLI_REMOTE_MEMORY_DIR", "")
    assert get_auto_mem_path(str(project)) == str(project / ".forgecli/memory") + os.sep


@pytest.mark.parametrize("name", ["config.yaml", "permissions.local.yaml", "skills/custom/SKILL.md"])
def test_sensitive_project_paths_are_protected(tmp_path, name):
    sandbox = PathSandbox(str(tmp_path))
    allowed, reason = sandbox.check_deny_write(str(tmp_path / ".forgecli" / name))
    assert not allowed
    assert reason


def test_project_source_files_remain_writable(tmp_path):
    sandbox = PathSandbox(str(tmp_path))
    assert sandbox.check_deny_write(str(tmp_path / "src/main.py")) == (True, "")


def test_memory_paths_do_not_depend_on_directory_existence(config_paths, monkeypatch):
    home, project = config_paths
    monkeypatch.delenv("FORGECLI_REMOTE_MEMORY_DIR", raising=False)
    expected_project = str(project / ".forgecli/memory") + os.sep
    expected_user = str(home / ".forgecli/memory") + os.sep
    assert get_auto_mem_path(str(project)) == expected_project
    assert get_user_auto_mem_path() == expected_user
    for base in (home, project):
        (base / ".forgecli/memory").mkdir(parents=True)
    assert get_auto_mem_path(str(project)) == expected_project
    assert get_user_auto_mem_path() == expected_user
