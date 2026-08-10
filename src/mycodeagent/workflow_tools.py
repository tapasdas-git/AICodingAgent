"""Deterministic Python tools exposed to the Omnigent supervisor."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .paths import ROOT
from .platform_utils import find_project_python
from .tracing import task_raw_trace_path, task_trace_path, write_trace, write_trace_output

ALLOWED_STAGE_EVENTS = {
    "IMPLEMENTATION_STARTED",
    "IMPLEMENTATION_COMPLETED",
    "IMPLEMENTATION_FAILED",
    "REVIEW_STARTED",
    "REVIEW_APPROVED",
    "REVIEW_CHANGES_REQUESTED",
    "TEST_FEEDBACK_RECEIVED_BY_SUPERVISOR",
    "REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR",
    "FEEDBACK_FORWARDED_TO_IMPLEMENTER",
    "ITERATION_LIMIT_REACHED",
}

EVENT_COMMENTARY = {
    "IMPLEMENTATION_STARTED": "Implementation started",
    "IMPLEMENTATION_COMPLETED": "Implementation completed",
    "IMPLEMENTATION_FAILED": "Implementation failed",
    "REVIEW_STARTED": "Review started",
    "REVIEW_APPROVED": "Review approved",
    "REVIEW_CHANGES_REQUESTED": "Review failed: changes requested",
    "TEST_FEEDBACK_RECEIVED_BY_SUPERVISOR": "Orchestrator received test failure feedback",
    "REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR": "Orchestrator received review feedback",
    "FEEDBACK_FORWARDED_TO_IMPLEMENTER": "Orchestrator forwarded feedback for remediation",
    "ITERATION_LIMIT_REACHED": "Iteration limit reached",
}

REMEDIATION_COMMENTARY = {
    "IMPLEMENTATION_STARTED": "Remediation started by supervisor",
    "IMPLEMENTATION_COMPLETED": "Remediation completed",
    "IMPLEMENTATION_FAILED": "Remediation failed",
}


def _event_commentary(event: str, iteration: int) -> str:
    if iteration > 1 and event in REMEDIATION_COMMENTARY:
        return REMEDIATION_COMMENTARY[event]
    return EVENT_COMMENTARY[event]


def _write_stage_event(trace_path: Path, event: str, iteration: int) -> None:
    """Write one readable live-commentary event."""
    write_trace(trace_path, f"{_event_commentary(event, iteration)} (iteration {iteration})")


def _last_stage_event(trace_path: Path) -> tuple[str, int | None] | None:
    """Return the latest live-commentary stage event."""
    commentary_to_event = {
        **{commentary: event for event, commentary in EVENT_COMMENTARY.items()},
        **{commentary: event for event, commentary in REMEDIATION_COMMENTARY.items()},
    }
    for line in reversed(trace_path.read_text(encoding="utf-8").splitlines()):
        message = line.split("] ", 1)[-1]
        for commentary, event in commentary_to_event.items():
            prefix = f"{commentary} (iteration "
            if message.startswith(prefix) and message.endswith(")"):
                iteration_text = message[len(prefix) : -1]
                if iteration_text.isdigit():
                    return event, int(iteration_text)
    return None


def record_stage_event(event: str, iteration: int) -> str:
    """Append an allowlisted supervisor lifecycle event to the active task trace."""
    task_id = os.environ.get("TASK_ID", "").strip()
    normalized_event = event.strip().upper()
    if not task_id:
        return json.dumps({"status": "error", "error": "TASK_ID is required"})
    if normalized_event not in ALLOWED_STAGE_EVENTS:
        return json.dumps({"status": "error", "error": "unsupported stage event"})
    if not isinstance(iteration, int) or isinstance(iteration, bool) or not 1 <= iteration <= 5:
        return json.dumps({"status": "error", "error": "iteration must be an integer from 1 through 5"})
    trace_path = task_trace_path(task_id)
    last_event = _last_stage_event(trace_path)
    if normalized_event == "REVIEW_STARTED" and last_event and last_event[0] == "IMPLEMENTATION_FAILED":
        stage = "remediation" if iteration > 1 else "implementation"
        write_trace(trace_path, f"Review blocked: {stage} failed (iteration {iteration})")
        return json.dumps(
            {"status": "error", "error": f"review cannot start after failed {stage}"}
        )
    if (
        normalized_event == "REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR"
        and last_event == ("REVIEW_STARTED", iteration)
    ):
        _write_stage_event(trace_path, "REVIEW_CHANGES_REQUESTED", iteration)
    if normalized_event in {"IMPLEMENTATION_STARTED", "REVIEW_STARTED"}:
        stage = (
            "remediation"
            if normalized_event == "IMPLEMENTATION_STARTED" and iteration > 1
            else "implementation"
            if normalized_event == "IMPLEMENTATION_STARTED"
            else "review"
        )
        write_trace(trace_path, f"Orchestrator triggered {stage} (iteration {iteration})")
    _write_stage_event(trace_path, normalized_event, iteration)
    if normalized_event == "FEEDBACK_FORWARDED_TO_IMPLEMENTER":
        write_trace(trace_path, f"Orchestrator triggered remediation (iteration {iteration})")
        _write_stage_event(trace_path, "IMPLEMENTATION_STARTED", iteration)
    return json.dumps({"status": "recorded", "event": normalized_event, "iteration": iteration})


def execute_task_tests() -> str:
    """Run the active task's isolated pytest suite and return a structured observation."""
    task_id = os.environ.get("TASK_ID", "").strip()
    task_dir = os.environ.get("TASK_DIR", "").strip()
    if not task_id or not task_dir:
        return json.dumps({"status": "error", "error": "TASK_ID and TASK_DIR are required"})

    workspace = (ROOT / task_dir).resolve()
    try:
        workspace.relative_to(ROOT)
    except ValueError:
        return json.dumps({"status": "error", "error": "TASK_DIR escapes the repository"})

    test_dir = workspace / "test"
    if not test_dir.is_dir():
        trace_path = task_trace_path(task_id)
        write_trace(trace_path, f"Tests blocked: configured test directory not found ({test_dir})")
        return json.dumps({"status": "error", "error": f"test directory not found: {test_dir}"})

    configured_python = os.environ.get("MYCODEAGENT_TEST_PYTHON", "").strip()
    python_executable = str(find_project_python(ROOT, configured_python or None))
    command = [python_executable, "-m", "pytest", "-q", str(test_dir)]
    test_environment = os.environ.copy()
    python_paths = [str(ROOT), str(ROOT / "src")]
    inherited_pythonpath = test_environment.get("PYTHONPATH", "").strip()
    if inherited_pythonpath:
        python_paths.append(inherited_pythonpath)
    test_environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    trace_path = task_trace_path(task_id)
    last_event = _last_stage_event(trace_path)
    if last_event and last_event[0] == "IMPLEMENTATION_STARTED":
        _write_stage_event(trace_path, "IMPLEMENTATION_COMPLETED", last_event[1] or 1)
    write_trace(trace_path, "Orchestrator triggered tests")
    write_trace(trace_path, "Tests started")
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=test_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        write_trace(trace_path, "Tests timed out")
        return json.dumps({"status": "timeout", "task_id": task_id, "command": command, "output": output})

    status = "passed" if completed.returncode == 0 else "failed"
    write_trace(trace_path, f"Tests {status} (exit code {completed.returncode})")
    if status == "failed":
        bounded_output = completed.stdout[-4000:].strip()
        write_trace_output(task_raw_trace_path(task_id), f"TEST_FAILURE_OUTPUT {bounded_output}\n")
    return json.dumps(
        {
            "status": status,
            "task_id": task_id,
            "command": command,
            "exit_code": completed.returncode,
            "output": completed.stdout,
        }
    )
