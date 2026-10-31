"""Verify release archives and run installed entry points outside the checkout."""

from __future__ import annotations

from email.parser import BytesParser
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_FILES = {
    "forgecli/styles.tcss",
    "forgecli/agents/builtins/explore.md",
    "forgecli/agents/builtins/general-purpose.md",
    "forgecli/agents/builtins/plan.md",
    "forgecli/agents/builtins/verification.md",
}
FORBIDDEN_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache",
    ".codex", ".agents", ".aws", ".playwright-mcp",
}
FORBIDDEN_NAMES = {
    "config.yaml", "config.local.yaml", "permissions.yaml",
    "permissions.local.yaml", "FORGECLI.local.md",
}


def check_paths(paths: set[str]) -> None:
    for name in sorted(paths):
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or FORBIDDEN_DIRS.intersection(path.parts)
            or path.name in FORBIDDEN_NAMES
            or path.name.startswith(".env")
            or path.suffix.lower() in {".pyc", ".log", ".pem", ".key", ".p12", ".pfx"}
        ):
            raise RuntimeError(f"Unexpected local or sensitive file in package: {name}")
        if ".forgecli" in path.parts and name != ".forgecli/config.yaml.example":
            raise RuntimeError(f"Unexpected runtime state in package: {name}")
    missing = RESOURCE_FILES - paths
    if missing:
        raise RuntimeError(f"Missing package resources: {sorted(missing)}")


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    wheel = ROOT / "dist" / f"forgecli-{version}-py3-none-any.whl"
    source = ROOT / "dist" / f"forgecli-{version}.tar.gz"

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        check_paths(names)
        metadata = BytesParser().parsebytes(archive.read(f"forgecli-{version}.dist-info/METADATA"))
        if metadata["Name"] != "forgecli" or metadata["Version"] != version:
            raise RuntimeError("Wheel metadata does not match pyproject.toml")
        if metadata["Description-Content-Type"] != "text/markdown":
            raise RuntimeError("Wheel metadata is missing the Markdown README")

    with tarfile.open(source, "r:gz") as archive:
        prefix = f"forgecli-{version}/"
        names = set()
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if not member.name.startswith(prefix):
                raise RuntimeError(f"Unexpected source archive path: {member.name}")
            names.add(member.name.removeprefix(prefix))
        check_paths(names)
        required = {
            "README.md", "pyproject.toml", "uv.lock", "tests/conftest.py",
            ".forgecli/config.yaml.example",
        }
        if required - names:
            raise RuntimeError(f"Missing source files: {sorted(required - names)}")

    # Use locked runtime dependencies, then install the wheel without the source
    # tree on sys.path. This catches missing data files and broken console scripts.
    with tempfile.TemporaryDirectory(prefix="forgecli-install-") as temporary:
        directory = Path(temporary)
        environment = directory / "venv"
        executable_dir = environment / ("Scripts" if sys.platform == "win32" else "bin")
        python = executable_dir / ("python.exe" if sys.platform == "win32" else "python")
        requirements = directory / "requirements.txt"
        run("uv", "export", "--locked", "--no-dev", "--no-emit-project", "--quiet",
            "--format", "requirements-txt", "--output-file", str(requirements))
        run("uv", "venv", "--python", sys.executable, str(environment))
        run("uv", "pip", "sync", "--python", str(python), str(requirements))
        run("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel))
        command = executable_dir / ("forgecli.exe" if sys.platform == "win32" else "forgecli")
        run(str(command), "--version", cwd=directory)
        run(str(python), "-m", "forgecli", "--help", cwd=directory)
        resource_check = (
            "from importlib.resources import files; import forgecli; "
            f"assert forgecli.__version__ == {version!r}; "
            "assert files('forgecli').joinpath('styles.tcss').read_text(encoding='utf-8'); "
            "assert files('forgecli.agents.builtins').joinpath('explore.md').read_text(encoding='utf-8')"
        )
        run(str(python), "-c", resource_check, cwd=directory)
    print("Distribution contents and isolated installation checks passed.")


if __name__ == "__main__":
    main()
