"""ForgeCLI state locations and project/user extension precedence."""

from pathlib import Path

import pytest

from forgecli.agents.loader import AgentLoader
from forgecli.commands.loader import load_user_commands
from forgecli.memory.session import SessionManager
from forgecli.paths import state_path
from forgecli.skills.loader import SkillLoader
from forgecli.worktree.manager import WorktreeManager


def test_state_paths_are_stable_and_do_not_modify_existing_data(tmp_path):
    target = tmp_path / ".forgecli" / "permissions.yaml"
    assert state_path(tmp_path, "permissions.yaml") == target
    assert not target.parent.exists()
    target.parent.mkdir()
    target.write_text("rules: []", encoding="utf-8")
    (target.parent / "skills").mkdir()
    assert state_path(tmp_path, "permissions.yaml") == target
    assert target.read_text(encoding="utf-8") == "rules: []"
    assert state_path(str(tmp_path), "sessions", "new.jsonl") == target.parent / "sessions/new.jsonl"
    assert not (target.parent / "sessions").exists()


@pytest.mark.parametrize("existing_directory", [False, True])
def test_sessions_are_created_and_listed_in_project_state(tmp_path, existing_directory):
    directory = tmp_path / ".forgecli" / "sessions"
    if existing_directory:
        directory.mkdir(parents=True)
    manager = SessionManager(str(tmp_path))
    session = manager.create()
    try:
        assert len(manager.list()) == 1
        assert len(list(directory.glob("*.jsonl"))) == 1
    finally:
        session.close()


def _write_extension(base, kind, name, description):
    directory = base / ".forgecli" / kind
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nExtension body\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("kind", ["skills", "agents", "commands"])
def test_extension_loaders_preserve_unique_names_and_project_priority(tmp_path, monkeypatch, kind):
    project = tmp_path / "project"
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    for base, scope in ((home, "user"), (project, "project")):
        _write_extension(base, kind, f"{scope}-only", f"{scope} extension")
        _write_extension(base, kind, "shared", f"{scope} shared extension")

    if kind == "skills":
        loader = SkillLoader(str(project))
        actual = {name: item.description for name, item in loader.load_all().items()}
        assert loader.get_source_label("project-only") == "project"
        assert loader.get_source_label("user-only") == "user"
        assert loader.get_source_label("shared") == "project"
    elif kind == "agents":
        definitions = AgentLoader(str(project)).load_all()
        actual = {name: item.when_to_use for name, item in definitions.items()}
        assert definitions["project-only"].source == "project"
        assert definitions["user-only"].source == "user"
        assert definitions["shared"].source == "project"
    else:
        commands = load_user_commands(str(project))
        actual = {item.name: item.description for item in commands}
        assert sum(command.name == "shared" for command in commands) == 1
    assert actual["user-only"] == "user extension"
    assert actual["project-only"] == "project extension"
    assert actual["shared"] == "project shared extension"


def test_worktree_state_uses_project_directory_with_unrelated_existing_state(tmp_path):
    directory = tmp_path / ".forgecli"
    (directory / "skills").mkdir(parents=True)
    manager = WorktreeManager(str(tmp_path))
    assert manager._forgecli_dir == directory
    assert Path(manager.worktree_dir) == directory / "worktrees"


def test_skill_reload_detects_new_project_directory_and_preserves_user_skills(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_extension(home, "skills", "user-only", "User skill")
    loader = SkillLoader(str(project))
    assert "user-only" in loader.load_all()
    assert not loader.needs_reload()
    _write_extension(project, "skills", "added", "Added project skill")
    assert loader.needs_reload()
    reloaded = loader.reload()
    assert reloaded["added"].description == "Added project skill"
    assert reloaded["user-only"].description == "User skill"
    assert loader.get_source_label("added") == "project"
    assert not loader.needs_reload()


def test_skill_install_target_uses_user_scope(tmp_path, monkeypatch):
    from forgecli.skills.install import user_skills_root

    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(project)
    assert user_skills_root() == home / ".forgecli" / "skills"
