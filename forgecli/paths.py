"""Resolve ForgeCLI's local state paths."""
from __future__ import annotations

from pathlib import Path


def state_path(base: str | Path, *parts: str) -> Path:
    """Return a path inside the base directory's .forgecli state directory."""
    return Path(base).joinpath(".forgecli", *parts)
