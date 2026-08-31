"""Tests for task worktree location configuration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from mycodeagent import tasks, worktrees


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


def test_registered_worktree_is_reused_for_task_retry() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir).resolve()
        existing = root / ".mycodeagent-worktrees" / "issue-23"
        existing.mkdir(parents=True)
        porcelain = (
            f"worktree {root}\nHEAD abc\nbranch refs/heads/main\n\n"
            f"worktree {existing}\nHEAD def\nbranch refs/heads/feature/issue-23\n"
        )
        with (
            patch.object(worktrees, "ROOT", root),
            patch.object(worktrees, "_branch_exists", return_value=True),
            patch.object(worktrees, "_git", return_value=porcelain),
        ):
            result = worktrees._create_worktree("ISSUE-23")

    assert result == existing


def test_incomplete_ready_task_is_marked_needs_detail_before_worktree_creation() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir).resolve()
        todo = root / "TODO.md"
        todo.write_text(
            "## TASK-701 | ready | P2 | Incomplete task in `workspace/incomplete/`\n"
            "### Outcome\nCreate a utility.\n",
            encoding="utf-8",
        )
        with (
            patch.object(tasks, "ROOT", root),
            patch.object(worktrees, "ROOT", root),
            patch.object(worktrees, "_create_worktree") as create_worktree,
        ):
            try:
                worktrees.run_submission_in_worktree(
                    todo,
                    task_id="TASK-701",
                    mode="2",
                    timeout_seconds=None,
                    token_budget=None,
                )
            except tasks.TaskReadinessError:
                pass
            else:
                raise AssertionError("incomplete ready task should be rejected")

        assert "## TASK-701 | needs_detail |" in todo.read_text(encoding="utf-8")
        create_worktree.assert_not_called()
