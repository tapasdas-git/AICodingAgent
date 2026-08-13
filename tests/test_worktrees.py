"""Tests for task worktree location configuration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from mycodeagent import worktrees


def test_worktree_root_comes_from_runtime_settings() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir).resolve()
        settings = root / "workflow_runtime.toml"
        settings.write_text('worktree_root = ".task-worktrees"\n', encoding="utf-8")

        with (
            patch.object(worktrees, "ROOT", root),
            patch.object(worktrees, "SETTINGS_PATH", settings),
            patch.dict(worktrees.os.environ, {}, clear=True),
        ):
            result = worktrees._worktree_path("TASK-008")

    assert result == root / ".task-worktrees" / "task-008"


def test_environment_worktree_root_overrides_runtime_settings() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir).resolve()
        settings = root / "workflow_runtime.toml"
        settings.write_text('worktree_root = ".task-worktrees"\n', encoding="utf-8")
        override = root / "override"

        with (
            patch.object(worktrees, "ROOT", root),
            patch.object(worktrees, "SETTINGS_PATH", settings),
            patch.dict(
                worktrees.os.environ,
                {"MYCODEAGENT_WORKTREE_ROOT": str(override)},
                clear=True,
            ),
        ):
            result = worktrees._worktree_path("TASK-008")

    assert result == override / "task-008"
