"""Repository-level paths and runtime constants."""

import os
from pathlib import Path


def _repository_root() -> Path:
    """Resolve the active checkout, including a Git worktree checkout."""
    configured_root = os.environ.get("MYCODEAGENT_ROOT")
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        if (candidate / "TODO.md").is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    return Path(__file__).resolve().parent.parent.parent


ROOT = _repository_root()
SETTINGS_PATH = Path(os.environ.get("MYCODEAGENT_SETTINGS_PATH", ROOT / "workflow_runtime.toml")).expanduser().resolve()
WORKFLOW_PATH = Path(os.environ.get("MYCODEAGENT_WORKFLOW_PATH", ROOT / "coding_agent.yaml")).expanduser().resolve()
TRACE_DIR = Path(os.environ.get("MYCODEAGENT_TRACE_DIR", ROOT / "logs")).expanduser().resolve()
ALLOWED_EFFORTS = {"low", "medium", "high"}
