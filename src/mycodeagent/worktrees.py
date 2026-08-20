"""Task-scoped Git worktree creation and isolated workflow launching."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .paths import ROOT, SETTINGS_PATH, TRACE_DIR
from .platform_utils import find_project_python, resolve_executable, restrict_file_permissions
from .tasks import get_task_section, get_task_spec, parse_todo_file, update_task_state


RUNTIME_OVERLAY_MODULES = ("tracing.py", "workflow_tools.py")


@contextmanager
def _runtime_module_overlay(workspace: Path) -> Iterator[None]:
    """Expose current deterministic tools in an origin-based worktree temporarily."""
    source_package = ROOT / "src" / "mycodeagent"
    target_package = workspace / "src" / "mycodeagent"
    originals: dict[Path, tuple[bytes, int]] = {}
    for module_name in RUNTIME_OVERLAY_MODULES:
        source = source_package / module_name
        target = target_package / module_name
        originals[target] = (target.read_bytes(), target.stat().st_mode)
        shutil.copy2(source, target)
    try:
        yield
    finally:
        for target, (content, mode) in originals.items():
            target.write_bytes(content)
            target.chmod(mode)


def _git(*arguments: str) -> str:
    git = resolve_executable("git")
    completed = subprocess.run(
        [git, "-C", str(ROOT), *arguments], text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(arguments)} failed")
    return completed.stdout.strip()


def _worktree_path(task_id: str) -> Path:
    """Resolve the configured task-worktree root with an environment override."""
    configured = os.environ.get("MYCODEAGENT_WORKTREE_ROOT", "").strip()
    if not configured:
        with SETTINGS_PATH.open("rb") as settings_file:
            configured = str(tomllib.load(settings_file).get("worktree_root", "")).strip()
    if configured:
        configured_path = Path(configured).expanduser()
        worktree_root = (
            configured_path.resolve()
            if configured_path.is_absolute()
            else (ROOT / configured_path).resolve()
        )
    else:
        worktree_root = ROOT.parent / ".mycodeagent-worktrees"
    return worktree_root / task_id.lower()


def _branch_exists(branch: str) -> bool:
    git = resolve_executable("git")
    return subprocess.run(
        [git, "-C", str(ROOT), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def _default_remote_branch() -> str:
    """Resolve origin's default branch with main/master fallbacks."""
    git = resolve_executable("git")
    symbolic = subprocess.run(
        [git, "-C", str(ROOT), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, check=False,
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip().startswith("origin/"):
        return symbolic.stdout.strip().split("/", 1)[1]
    for branch in ("main", "master"):
        if subprocess.run(
            [git, "-C", str(ROOT), "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0:
            return branch
    raise RuntimeError("Could not resolve origin's default branch (expected origin/HEAD, main, or master)")


def _create_worktree(task_id: str) -> Path:
    branch = f"feature/{task_id.lower()}"
    destination = _worktree_path(task_id)
    if destination.exists():
        raise RuntimeError(f"Worktree path already exists: {destination}")
    if _branch_exists(branch):
        raise RuntimeError(f"Branch already exists: {branch}. Reuse or remove its existing worktree explicitly.")

    _git("fetch", "origin")
    base_branch = _default_remote_branch()
    base_revision = _git("rev-parse", "--verify", f"origin/{base_branch}^{{commit}}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _git("worktree", "add", "-b", branch, str(destination), base_revision)
    return destination


def _write_work_order(workspace: Path, todo_path: Path, task_id: str) -> tuple[Path, str]:
    """Freeze only the selected task where the isolated agent can read it."""
    work_order_dir = workspace / ".mycodeagent" / "work-orders"
    work_order_dir.mkdir(parents=True, exist_ok=True)
    work_order = work_order_dir / f"{task_id}.md"
    section = get_task_section(todo_path, task_id)
    work_order.write_text(section, encoding="utf-8")
    restrict_file_permissions(work_order)
    visible_todo = workspace / "TODO.md"
    original_todo = visible_todo.read_text(encoding="utf-8")
    if f"## {task_id} |" not in original_todo:
        visible_todo.write_text(
            original_todo.rstrip() + "\n\n<!-- MyCodeAgent active work order; removed after this run. -->\n\n" + section,
            encoding="utf-8",
        )
    return work_order, original_todo


def run_submission_in_worktree(
    todo_path: Path, *, task_id: str, mode: str, timeout_seconds: int | None,
    token_budget: int | None,
) -> int:
    """Run one selected ready task in a worktree from origin's default branch."""
    task_id = task_id.upper()
    task = get_task_spec(todo_path, task_id)
    if task.state != "ready":
        raise ValueError(f"Task {task_id} must be in state 'ready' to create a worktree")

    workspace = _create_worktree(task_id)
    work_order, original_workspace_todo = _write_work_order(workspace, todo_path, task_id)
    if not update_task_state(todo_path, task_id, "working", expected_state="ready"):
        raise RuntimeError(f"Could not mark {task_id} working after creating its worktree")

    command = [sys.executable, "-m", "mycodeagent", "submit", "--todo", str(work_order), "--mode", mode]
    if timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(timeout_seconds)])
    if token_budget is not None:
        command.extend(["--token-budget", str(token_budget)])
    environment = os.environ.copy()
    runtime_source = str(ROOT / "src")
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment.update({
        "MYCODEAGENT_ROOT": str(workspace),
        "MYCODEAGENT_PRIMARY_TODO_PATH": str(todo_path.resolve()),
        "MYCODEAGENT_TRACE_DIR": str(TRACE_DIR),
        "MYCODEAGENT_SETTINGS_PATH": str(ROOT / "workflow_runtime.toml"),
        "MYCODEAGENT_WORKFLOW_PATH": str(ROOT / "coding_agent.yaml"),
        "MYCODEAGENT_HELPER_PATH": str(ROOT / "scripts" / "workflow_helpers.py"),
        "MYCODEAGENT_APPROVAL_PATH": str(ROOT / "git_approval.toml"),
        "MYCODEAGENT_TEST_PYTHON": str(find_project_python(ROOT)),
        # A clean origin-default worktree may not contain the latest uncommitted
        # workflow runtime modules. Put the launcher runtime first so both the
        # child CLI and Omnigent dotted Python tools resolve the same version.
        "PYTHONPATH": (
            runtime_source
            if not inherited_pythonpath
            else os.pathsep.join((runtime_source, inherited_pythonpath))
        ),
    })
    print(f"Worktree: {workspace}")
    print(f"Branch: feature/{task_id.lower()}")
    try:
        with _runtime_module_overlay(workspace):
            try:
                completed = subprocess.run(command, cwd=workspace, env=environment, check=False)
            except OSError as exc:
                update_task_state(todo_path, task_id, "failed", expected_state="working")
                raise RuntimeError(f"Could not start isolated task workflow: {exc}") from exc
    finally:
        (workspace / "TODO.md").write_text(original_workspace_todo, encoding="utf-8")

    child_state = parse_todo_file(work_order).get(task_id, {}).get("state", "failed")
    if child_state not in {"implemented", "reviewed", "delivered", "failed"}:
        child_state = "failed"
    primary_state = parse_todo_file(todo_path).get(task_id, {}).get("state")
    if primary_state != child_state and not update_task_state(
        todo_path, task_id, child_state, expected_state="working"
    ):
        raise RuntimeError(f"Worktree completed, but primary TODO state for {task_id} could not be updated")
    return completed.returncode
