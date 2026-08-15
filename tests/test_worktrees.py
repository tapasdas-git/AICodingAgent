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


def test_runtime_module_overlay_uses_current_tools_and_restores_worktree() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir).resolve()
        workspace = root / "worktree"
        source_package = root / "src" / "mycodeagent"
        target_package = workspace / "src" / "mycodeagent"
        source_package.mkdir(parents=True)
        target_package.mkdir(parents=True)
        for module_name in worktrees.RUNTIME_OVERLAY_MODULES:
            (source_package / module_name).write_text(
                f"current {module_name}\n", encoding="utf-8"
            )
            (target_package / module_name).write_text(
                f"stale {module_name}\n", encoding="utf-8"
            )

        with patch.object(worktrees, "ROOT", root):
            with worktrees._runtime_module_overlay(workspace):
                for module_name in worktrees.RUNTIME_OVERLAY_MODULES:
                    assert (target_package / module_name).read_text(
                        encoding="utf-8"
                    ) == f"current {module_name}\n"

        for module_name in worktrees.RUNTIME_OVERLAY_MODULES:
            assert (target_package / module_name).read_text(
                encoding="utf-8"
            ) == f"stale {module_name}\n"
