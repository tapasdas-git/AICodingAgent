"""Deterministic changelog and pull-request delivery after an approved review."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import ROOT
from .platform_utils import repository_relative_posix, resolve_executable
from .tasks import TaskSpec, parse_todo_file, update_task_state
from .tracing import task_raw_trace_path, task_trace_path, write_trace, write_trace_output


def _run_helper(command: list[str], *, timeout_seconds: int, trace_path) -> tuple[int, str]:
    raw_trace_path = task_raw_trace_path(trace_path.stem)
    try:
        completed = subprocess.run(
            command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        write_trace_output(raw_trace_path, output)
        return 124, output
    write_trace_output(raw_trace_path, completed.stdout)
    return completed.returncode, completed.stdout


def _helper_path() -> Path:
    """Use the launcher-provided current helper, not an older worktree copy."""
    configured = os.environ.get("MYCODEAGENT_HELPER_PATH")
    helper = Path(configured) if configured else ROOT / "scripts" / "workflow_helpers.py"
    if not helper.is_file():
        raise RuntimeError(f"Delivery helper not found: {helper}")
    return helper.resolve()


def _approval_path() -> Path:
    configured = os.environ.get("MYCODEAGENT_APPROVAL_PATH")
    approval = Path(configured) if configured else ROOT / "git_approval.toml"
    if not approval.is_file():
        raise RuntimeError(f"Git approval policy not found: {approval}")
    return approval.resolve()


def run_approved_delivery(task: TaskSpec, *, timeout_seconds: int) -> int:
    """Run deterministic changelog and PR helpers for an already approved task."""
    trace_path = task_trace_path(task.task_id)
    try:
        git = resolve_executable("git")
    except RuntimeError as exc:
        write_trace(trace_path, f"DELIVERY_REFUSED reason={exc}")
        print(f"# Delivery\n## Outcome\n- Status: refused\n- Reason: {exc}")
        return 1
    changelog_status = subprocess.run(
        [git, "status", "--porcelain", "--", "CHANGELOG.md"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    changelog_already_prepared = False
    if changelog_status.returncode == 0 and changelog_status.stdout.strip():
        changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        changelog_already_prepared = f"**{task.task_id}**" in changelog_text
    if changelog_status.returncode != 0 or (changelog_status.stdout.strip() and not changelog_already_prepared):
        write_trace(trace_path, "DELIVERY_REFUSED reason=changelog_has_uncommitted_changes")
        print("# Delivery\n## Outcome\n- Status: refused\n- Reason: CHANGELOG.md has uncommitted changes.")
        return 1

    helper = _helper_path()
    helper_prefix = [
        sys.executable, str(helper), "--repo-root", str(ROOT),
        "--approval-file", str(_approval_path()),
    ]
    if changelog_already_prepared:
        write_trace(trace_path, f"DELIVERY_CHANGELOG_RESUMED task={task.task_id}")
    else:
        changelog_command = [*helper_prefix, "changelog", "--task-id", task.task_id]
        write_trace(trace_path, f"DELIVERY_CHANGELOG_STARTED task={task.task_id}")
        changelog_code, _ = _run_helper(changelog_command, timeout_seconds=timeout_seconds, trace_path=trace_path)
        if changelog_code != 0:
            write_trace(trace_path, f"DELIVERY_CHANGELOG_FAILED exit_code={changelog_code}")
            print(f"# Delivery\n## Changelog\n- Status: failed (exit code {changelog_code})")
            return changelog_code

    task_dir = repository_relative_posix(task.workspace, ROOT)
    pr_command = [
        *helper_prefix, "pr", "--task-id", task.task_id,
        "--task-dir", task_dir, "--review-status", "APPROVED",
    ]
    write_trace(trace_path, f"DELIVERY_PR_STARTED task={task.task_id}")
    pr_code, pr_output = _run_helper(pr_command, timeout_seconds=timeout_seconds, trace_path=trace_path)
    if pr_code != 0:
        write_trace(trace_path, f"DELIVERY_PR_FAILED exit_code={pr_code}")
        print(f"# Delivery\n## Pull request\n- Status: failed (exit code {pr_code})")
        return pr_code

    primary_todo_value = os.environ.get("MYCODEAGENT_PRIMARY_TODO_PATH")
    if primary_todo_value:
        primary_todo_path = Path(primary_todo_value).resolve()
        primary_state = parse_todo_file(primary_todo_path).get(task.task_id, {}).get("state")
        if primary_state != "delivered" and not update_task_state(
            primary_todo_path, task.task_id, "delivered", expected_state="working"
        ):
            write_trace(trace_path, "DELIVERY_STATE_UPDATE_FAILED requested_state=delivered")
            print("# Delivery\n## Task state\n- Status: failed to mark task delivered")
            return 1

    url = next((line.strip() for line in pr_output.splitlines() if line.strip().startswith("http")), "created")
    write_trace(trace_path, "DELIVERY_COMPLETED status=success")
    print(f"# Delivery\n## Changelog\n- Status: updated\n## Pull request\n- Status: created\n- URL: {url}")
    return 0
