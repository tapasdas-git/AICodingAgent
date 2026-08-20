"""Persistent-supervisor workflow orchestration."""

from __future__ import annotations

from pathlib import Path

from .runner import WorkflowResult, execute_omnigent_stage
from .tasks import TaskSpec


def review_verdict(report: str | None) -> str | None:
    """Extract the terminal review verdict from a structured stage report."""
    if report is None:
        return None
    if "Final review: APPROVED" in report or report.lstrip().startswith("APPROVED"):
        return "APPROVED"
    if "Final review: CHANGES_REQUESTED" in report or report.lstrip().startswith(
        "CHANGES_REQUESTED"
    ):
        return "CHANGES_REQUESTED"
    return None


def report_failed(report: str | None) -> bool:
    """Recognize a protocol-valid report whose workflow outcome is failure."""
    return report is not None and "- Status: failed" in report


def execute_staged_verification(
    *,
    task: TaskSpec,
    todo_path: Path,
    timeout_seconds: int | None,
    token_budget: int | None,
    implement_first: bool,
    remediate: bool,
) -> WorkflowResult:
    """Run one supervisor session that selects and sequences all agent tools."""
    if implement_first:
        mode = "IMPLEMENT AND REVIEW ONLY"
        instruction = (
            f"Execute the bounded implementation, test, review, remediation, and final-review "
            f"loop for {task.task_id}. Keep all stage observations in this supervisor context."
        )
    elif remediate:
        mode = "REVIEW AND REMEDIATE ONLY"
        instruction = (
            f"Review {task.task_id}; if changes are requested, pass the complete findings to "
            "the implementer once and then re-review in this same supervisor context."
        )
    else:
        mode = "REVIEW ONLY"
        instruction = f"Review {task.task_id} once without changing files."

    return execute_omnigent_stage(
        f"{mode}\n{instruction}\nDo not perform delivery.",
        timeout_seconds=timeout_seconds,
        token_budget=token_budget,
        task=task,
        todo_path=todo_path,
    )
