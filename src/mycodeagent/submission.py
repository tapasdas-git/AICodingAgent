"""One-task and explicit batch submission with one supervisor per task."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .delivery import run_approved_delivery
from .orchestration import execute_staged_verification, report_failed, review_verdict
from .runner import execute_omnigent_stage
from .tasks import (
    TaskReadinessError,
    get_first_ready_task,
    get_task_spec,
    parse_todo_file,
    update_task_state,
)
from .tracing import task_trace_path, write_trace

MODE_PLANS = {
    "1": "implementation only",
    "2": "persistent supervisor: implementation -> tests -> review -> bounded feedback loop",
    "3": "persistent supervisor: implementation -> tests -> review -> bounded feedback loop -> pull request",
}


def final_review_is_approved(report: str | None) -> bool:
    """Allow deterministic delivery only after the final review says APPROVED."""
    return review_verdict(report) == "APPROVED"


def submit_ready_queue(
    todo_path: Path, *, timeout_seconds: int | None, token_budget: int | None,
    once: bool, stop_on_error: bool, mode: str
) -> int:
    """Process the first ready task, or an explicitly requested sequential batch."""
    processed = failures = 0
    while True:
        try:
            tasks = parse_todo_file(todo_path)
        except TaskReadinessError as exc:
            print(f"Task readiness failed: {exc}", file=sys.stderr)
            if not update_task_state(todo_path, task_id, "needs_detail", expected_state="ready"):
                print(f"Could not mark {task_id} as needs_detail; stopping submission.", file=sys.stderr)
                return 1
            failures += 1
            processed += 1
            if once or stop_on_error:
                break
            continue
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        task_id = get_first_ready_task(tasks)
        if task_id is None:
            if processed == 0:
                print("No task with state 'ready' found in TODO.md.", file=sys.stderr)
                return 1
            break
        try:
            task = get_task_spec(todo_path, task_id)
        except ValueError as exc:
            print(f"Task {task_id} cannot be run: {exc}", file=sys.stderr)
            if not update_task_state(todo_path, task_id, "failed", expected_state="ready"):
                print(f"Could not mark {task_id} as failed; stopping submission.", file=sys.stderr)
                return 1
            failures += 1
            processed += 1
            if once or stop_on_error:
                break
            continue
        if not update_task_state(todo_path, task_id, "working", expected_state="ready"):
            print(f"Task {task_id} changed before it could be started; reloading TODO.md.")
            continue

        trace_path = task_trace_path(task.task_id)
        write_trace(trace_path, "SUBMISSION_STARTED state=working")
        print(f"{'Running task' if once else f'Queue task {processed + 1}'}: {task_id} — {task.title}")
        print(f"Mode {mode}: {MODE_PLANS[mode]}")
        success_state = "reviewed"
        if mode == "1":
            success_state = "implemented"
            prompt = f"Implement {task_id} only. Do not review, update the changelog, or create a pull request."
        elif mode == "2":
            print("Pull request: not created by mode 2.")
        else:
            print("Pull request: created deterministically only after a verified APPROVED review.")

        if mode == "1":
            workflow_result = execute_omnigent_stage(
                prompt, target_stage="implement_task", timeout_seconds=timeout_seconds,
                token_budget=token_budget, task=task, todo_path=todo_path,
            )
        else:
            workflow_result = execute_staged_verification(
                task=task, todo_path=todo_path, timeout_seconds=timeout_seconds,
                token_budget=token_budget,
                implement_first=True, remediate=True,
            )
        return_code = workflow_result.exit_code
        if return_code == 0 and report_failed(workflow_result.report):
            return_code = 1
        final_state = success_state if return_code == 0 else "failed"
        if mode == "3" and return_code == 0:
            if final_review_is_approved(workflow_result.report):
                delivery_code = run_approved_delivery(task, timeout_seconds=timeout_seconds or 600)
                return_code = delivery_code
                final_state = "delivered" if delivery_code == 0 else "reviewed"
            else:
                print("# Delivery\n## Outcome\n- Status: skipped\n- Reason: final review was not APPROVED.")
                final_state = "reviewed"
                return_code = 1
        if not update_task_state(todo_path, task_id, final_state, expected_state="working"):
            write_trace(trace_path, f"SUBMISSION_STATE_UPDATE_FAILED requested_state={final_state}")
            print(f"Workflow for {task_id} ended, but its TODO state could not be updated; stopping submission.", file=sys.stderr)
            return 1
        primary_todo_value = os.environ.get("MYCODEAGENT_PRIMARY_TODO_PATH")
        if primary_todo_value:
            primary_todo_path = Path(primary_todo_value).resolve()
            primary_state = parse_todo_file(primary_todo_path).get(task_id, {}).get("state")
            if (
                primary_todo_path != todo_path.resolve()
                and primary_state != final_state
                and not update_task_state(
                    primary_todo_path, task_id, final_state, expected_state="working"
                )
            ):
                write_trace(
                    trace_path,
                    f"SUBMISSION_PRIMARY_STATE_UPDATE_FAILED requested_state={final_state}",
                )
                print(
                    f"Workflow for {task_id} ended, but its primary TODO state could not be updated; "
                    "stopping submission.",
                    file=sys.stderr,
                )
                return 1
        write_trace(trace_path, f"SUBMISSION_FINISHED state={final_state} submission_exit_code={return_code}")
        processed += 1
        if return_code:
            failures += 1
            if final_state == "failed":
                print(f"Task {task_id} failed and was marked failed.", file=sys.stderr)
            else:
                print(f"Task {task_id} stopped before delivery and was marked {final_state}.", file=sys.stderr)
            if stop_on_error:
                break
        else:
            print(f"Task {task_id} finished and was marked {final_state}.")
        if once:
            break
    print(f"Submission finished: processed={processed}, failed={failures}.")
    return 1 if failures else 0
