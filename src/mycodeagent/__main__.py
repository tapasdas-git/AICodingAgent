#!/usr/bin/env python3
"""CLI argument routing for MyCodeAgent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .delivery import run_approved_delivery
from .orchestration import execute_staged_verification
from .paths import ROOT
from .runner import execute_omnigent_stage, positive_timeout
from .submission import submit_ready_queue
from .tasks import get_task_spec, parse_todo_file
from .worktrees import run_submission_in_worktree


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser without performing workflow work."""
    parser = argparse.ArgumentParser(prog="mycodeagent", description="MyCodeAgent Workflow CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    submit_parser = subparsers.add_parser("submit", help="Run the first ready task in TODO.md order")
    submit_parser.add_argument("--todo", type=Path, default=ROOT / "TODO.md", help="Path to TODO.md file")
    submit_parser.add_argument("--mode", choices=("1", "2", "3"), default="2", help="1=implementation only; 2=implementation and review (default); 3=implementation, review, and PR.")
    submit_parser.add_argument("--all", action="store_true", help="Explicitly process all ready tasks sequentially (default: one task only).")
    submit_parser.add_argument("--task-id", help="Select one ready task explicitly (required with --worktree when multiple tasks are ready).")
    submit_parser.add_argument("--worktree", action="store_true", help="Create an isolated feature worktree from origin's default branch for one task.")
    submit_parser.add_argument("--stop-on-error", action="store_true", help="Stop the queue after the first failed task (default: continue to later tasks).")
    submit_parser.add_argument("--timeout-seconds", type=positive_timeout, default=None, help="Maximum runtime for the complete supervisor workflow.")

    for stage_cmd in ("run", "verify", "review", "deliver"):
        stage_parser = subparsers.add_parser(stage_cmd, help=f"Run the '{stage_cmd}' workflow stage")
        stage_parser.add_argument("task_id", help="Task ID (e.g., TASK-101)")
        stage_parser.add_argument("--todo", type=Path, default=ROOT / "TODO.md", help="Path to TODO.md file")
        stage_parser.add_argument("--timeout-seconds", type=positive_timeout, default=None, help="Maximum runtime for the selected workflow invocation.")
        if stage_cmd == "deliver":
            stage_parser.add_argument("--approved", action="store_true", help="Explicitly authorize delivery after an APPROVED review.")
        if stage_cmd == "review":
            stage_parser.add_argument("--remediate", action="store_true", help="Make one targeted fix attempt after findings, then re-review.")
    return parser


def main() -> int:
    # Parse the requested CLI operation and its task/workflow options.
    args = build_parser().parse_args()
    if not args.command:
        build_parser().print_help()
        return 1

    # Load the task registry once so every command works from the same TODO view.
    try:
        tasks = parse_todo_file(args.todo)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.command == "submit":
        # Guard queue/worktree combinations before starting any task work.
        if args.all and args.mode == "3":
            print("Refusing batch delivery: mode 3 may create a PR for only one explicitly selected task.", file=sys.stderr)
            return 1
        if args.worktree:
            # Run one selected ready task in an isolated branch and worktree.
            if args.all:
                print("Refusing --all with --worktree; start one task worktree per command.", file=sys.stderr)
                return 1
            selected_task = (args.task_id or next((task_id for task_id, info in tasks.items() if info["state"] == "ready"), None))
            if selected_task is None:
                print("No task with state 'ready' found in TODO.md.", file=sys.stderr)
                return 1
            try:
                return run_submission_in_worktree(args.todo, task_id=selected_task, mode=args.mode, timeout_seconds=args.timeout_seconds)
            except (RuntimeError, ValueError) as exc:
                print(f"Worktree workflow refused: {exc}", file=sys.stderr)
                return 1
        # Submit one ready task by default, or a sequential queue with --all.
        return submit_ready_queue(args.todo, timeout_seconds=args.timeout_seconds, once=not args.all, stop_on_error=args.stop_on_error, mode=args.mode)

    # Resolve and validate the explicitly named task for stage-level commands.
    target_task = args.task_id.upper()
    if target_task not in tasks:
        print(f"Task ID '{target_task}' not found in {args.todo.name}.", file=sys.stderr)
        return 1
    try:
        task = get_task_spec(args.todo, target_task)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.command == "verify":
        # Keep implementation, review, remediation, and re-review in one supervisor context.
        print(f"Running implementation and review loop for {target_task} without delivery...")
        return execute_staged_verification(
            task=task, todo_path=args.todo, timeout_seconds=args.timeout_seconds,
            implement_first=True, remediate=True,
        ).exit_code
    if args.command == "review":
        # Run either a read-only review or one bounded review/remediation cycle.
        if args.remediate:
            print(f"Running review and targeted remediation loop for {target_task} without delivery...")
            return execute_staged_verification(
                task=task, todo_path=args.todo, timeout_seconds=args.timeout_seconds,
                implement_first=False, remediate=True,
            ).exit_code
        else:
            print(f"Running read-only review for {target_task} without remediation or delivery...")
            return execute_omnigent_stage(
                f"Review {target_task} once and return APPROVED or CHANGES_REQUESTED. Do not modify files or perform delivery.",
                target_stage="review_change", timeout_seconds=args.timeout_seconds,
                task=task, todo_path=args.todo,
            ).exit_code
    if args.command == "deliver" and not args.approved:
        # Require explicit operator approval before any Git/GitHub side effect.
        print("Refusing delivery: re-run with --approved after an APPROVED review result.", file=sys.stderr)
        return 1

    if args.command == "deliver":
        # Delegate approved changelog, commit, push, and PR work to Python delivery.
        return run_approved_delivery(task, timeout_seconds=args.timeout_seconds or 600)

    if args.command == "run":
        # Invoke only the implementation stage for focused troubleshooting.
        print(f"Running implementation stage for {target_task}...")
        return execute_omnigent_stage(
            f"Target stage troubleshooting for {target_task} using implement_task.",
            target_stage="implement_task", timeout_seconds=args.timeout_seconds, task=task, todo_path=args.todo,
        ).exit_code


if __name__ == "__main__":
    raise SystemExit(main())
