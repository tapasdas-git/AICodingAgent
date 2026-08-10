"""Cross-platform process, interpreter, path, and permission helpers."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_executable(command: str) -> str:
    """Resolve a configured executable name or path with a clear failure."""
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        if candidate.is_file():
            return str(candidate.resolve())
        raise RuntimeError(f"Executable not found: {candidate}")
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(f"Required executable is not available on PATH: {command}")
    return resolved


def find_project_python(root: Path, configured: str | None = None) -> Path:
    """Find the configured or conventional project interpreter on any OS."""
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve()
    candidates = (
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "bin" / "python",
        root / ".venv" / "bin" / "python",
    )
    return next((path.resolve() for path in candidates if path.is_file()), Path(sys.executable).resolve())


def repository_relative_posix(path: Path, root: Path) -> str:
    """Return a Git-compatible repository-relative path on every OS."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def restrict_file_permissions(path: Path) -> None:
    """Apply owner-only POSIX permissions without breaking Windows execution."""
    if os.name == "posix":
        path.chmod(0o600)
