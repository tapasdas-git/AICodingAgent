"""Deterministic Python tools exposed to the Omnigent supervisor."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
from pathlib import Path

from .paths import ROOT
from .platform_utils import find_project_python
from .tracing import (
    task_raw_trace_path,
    task_trace_path,
    test_result_logging_enabled,
    test_trace_path,
    token_usage_path,
    write_trace,
    write_trace_output,
)

TOKEN_AGENTS = {"supervisor", "implementer", "reviewer"}
REPORT_OUTCOMES = {"COMPLETED", "FAILED", "APPROVED", "CHANGES_REQUESTED", "REMEDIATE", "BLOCKED"}


def record_agent_report(agent: str, iteration: int, outcome: str, report: str) -> str:
    """Persist a full redacted, deduplicated agent report in the raw log."""
    task_id = os.environ.get("TASK_ID", "").strip()
    agent, outcome = agent.strip().lower(), outcome.strip().upper()
    if not task_id or agent not in TOKEN_AGENTS or outcome not in REPORT_OUTCOMES:
        return json.dumps({"status": "error", "error": "invalid task, agent, or outcome"})
    if not isinstance(iteration, int) or isinstance(iteration, bool) or not 1 <= iteration <= 5:
        return json.dumps({"status": "error", "error": "iteration must be 1 through 5"})
    if not isinstance(report, str) or not report.strip() or len(report) > 200_000:
        return json.dumps({"status": "error", "error": "report must contain 1 through 200000 characters"})
    report = report.strip()
    digest = hashlib.sha256(f"{agent}\0{iteration}\0{outcome}\0{report}".encode()).hexdigest()[:16]
    marker = f"===== AGENT_REPORT task={task_id} agent={agent} iteration={iteration} outcome={outcome} digest={digest} ====="
    raw_path = task_raw_trace_path(task_id)
    if marker in raw_path.read_text(encoding="utf-8"):
        return json.dumps({"status": "already_recorded", "digest": digest})
    write_trace_output(raw_path, f"\n{marker}\n{report}\n===== END_AGENT_REPORT digest={digest} =====\n")
    write_trace(task_trace_path(task_id), f"Agent report persisted: agent={agent} iteration={iteration} outcome={outcome} digest={digest}")
    return json.dumps({"status": "recorded", "digest": digest})


def record_token_usage(agent: str, iteration: int, tokens_used: int) -> str:
    """Aggregate native goal usage across supervisor and child agents."""
    task_id = os.environ.get("TASK_ID", "").strip()
    agent = agent.strip().lower()
    if not task_id or agent not in TOKEN_AGENTS:
        return json.dumps({"status": "error", "error": "invalid task or agent"})
    if not isinstance(iteration, int) or isinstance(iteration, bool) or not 1 <= iteration <= 5:
        return json.dumps({"status": "error", "error": "iteration must be 1 through 5"})
    if not isinstance(tokens_used, int) or isinstance(tokens_used, bool) or tokens_used < 0:
        return json.dumps({"status": "error", "error": "tokens_used must be non-negative"})
    if agent != "supervisor" and tokens_used == 0:
        return json.dumps({"status": "error", "error": "zero child usage was not measured"})
    path = token_usage_path(task_id)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.dumps({"status": "error", "error": "token ledger unavailable"})
    snapshots, children = ledger.setdefault("supervisor_snapshots", {}), ledger.setdefault("children", {})
    previous = max((int(v) for v in snapshots.values()), default=0)
    delta = 0
    if agent == "supervisor":
        if tokens_used < previous:
            return json.dumps({"status": "error", "error": "supervisor usage cannot decrease"})
        delta = tokens_used - previous
        snapshots[str(iteration)] = tokens_used
    else:
        key = f"{agent}:{iteration}"
        if key in children and children[key] != tokens_used:
            return json.dumps({"status": "error", "error": f"usage already recorded for {key}"})
        children[key] = tokens_used
    supervisor_total = max((int(v) for v in snapshots.values()), default=0)
    child_total = sum(int(v) for v in children.values())
    total, budget = supervisor_total + child_total, int(ledger["budget"])
    prior_iteration = max((int(v) for k, v in snapshots.items() if int(k) < iteration), default=0)
    iteration_supervisor = int(snapshots.get(str(iteration), prior_iteration)) - prior_iteration
    iteration_children = sum(int(v) for k, v in children.items() if k.endswith(f":{iteration}"))
    remaining = max(0, budget - total)
    caps = {name: int(os.environ[f"MYCODEAGENT_{name.upper()}_TOKEN_BUDGET"]) for name in TOKEN_AGENTS}
    cap, agent_remaining = caps[agent], max(0, caps[agent] - tokens_used)
    agent_status = "exhausted" if tokens_used >= cap else "active"
    task_status = "exhausted" if total >= budget else "active"
    ledger.update(supervisor_tokens=supervisor_total, child_tokens=child_total, total_tokens=total, remaining_tokens=remaining, exhausted=total >= budget)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if agent == "supervisor":
        message = f"Token usage snapshot (iteration {iteration}): agent=supervisor cumulative_tokens={tokens_used} delta_since_last_snapshot={delta} iteration_supervisor_tokens={iteration_supervisor} iteration_total={iteration_supervisor + iteration_children}"
    else:
        message = f"Child token usage (iteration {iteration}): agent={agent} invocation_tokens={tokens_used} iteration_child_tokens={iteration_children} iteration_total={iteration_supervisor + iteration_children}"
    write_trace(task_trace_path(task_id), f"{message} agent_budget={cap} agent_remaining={agent_remaining} agent_status={agent_status} task_total={total}/{budget} task_remaining={remaining} task_status={task_status}")
    return json.dumps({"status": "exhausted" if total >= budget or tokens_used >= cap else "recorded", "iteration_tokens": iteration_supervisor + iteration_children, "total_tokens": total, "remaining_tokens": remaining, "implementer_limit": min(caps["implementer"], remaining), "reviewer_limit": min(caps["reviewer"], remaining)})

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


def _stage_event_history(trace_path: Path) -> list[tuple[str, int]]:
    """Return current-workflow live-commentary stage events in trace order."""
    commentary_to_event = {
        **{commentary: event for event, commentary in EVENT_COMMENTARY.items()},
        **{commentary: event for event, commentary in REMEDIATION_COMMENTARY.items()},
    }
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    workflow_start = next(
        (
            index
            for index in range(len(lines) - 1, -1, -1)
            if lines[index].split("] ", 1)[-1].startswith("WORKFLOW_STARTED ")
        ),
        -1,
    )
    history: list[tuple[str, int]] = []
    for line in lines[workflow_start + 1 :]:
        message = line.split("] ", 1)[-1]
        for commentary, event in commentary_to_event.items():
            prefix = f"{commentary} (iteration "
            if message.startswith(prefix) and message.endswith(")"):
                iteration_text = message[len(prefix) : -1]
                if iteration_text.isdigit():
                    history.append((event, int(iteration_text)))
                    break
    return history


def _last_stage_event(trace_path: Path) -> tuple[str, int | None] | None:
    """Return the latest live-commentary stage event."""
    history = _stage_event_history(trace_path)
    return history[-1] if history else None


def _stage_transition_error(
    history: list[tuple[str, int]], event: str, iteration: int
) -> str | None:
    """Reject stale, skipped, or out-of-order supervisor lifecycle events."""
    if not history:
        if event not in {"IMPLEMENTATION_STARTED", "REVIEW_STARTED"} or iteration != 1:
            return "the first stage event must start implementation or review at iteration 1"
        return None

    latest_iteration = history[-1][1]
    if iteration < latest_iteration:
        return f"cannot record iteration {iteration}; current iteration is {latest_iteration}"
    if iteration > latest_iteration + 1:
        return f"cannot skip from iteration {latest_iteration} to iteration {iteration}"
    if (event, iteration) in history:
        return None

    events = {recorded_event for recorded_event, recorded_iteration in history if recorded_iteration == iteration}
    implementation_terminal = events & {"IMPLEMENTATION_COMPLETED", "IMPLEMENTATION_FAILED"}
    review_terminal = events & {"REVIEW_APPROVED", "REVIEW_CHANGES_REQUESTED"}

    if event == "IMPLEMENTATION_STARTED":
        if iteration == 1 or ("FEEDBACK_FORWARDED_TO_IMPLEMENTER", iteration) not in history:
            return "remediation can start only after feedback is forwarded for the same iteration"
    elif event in {"IMPLEMENTATION_COMPLETED", "IMPLEMENTATION_FAILED"}:
        if "IMPLEMENTATION_STARTED" not in events:
            return "implementation must start before it can finish"
        if implementation_terminal:
            return "implementation already has a terminal event for this iteration"
        if "REVIEW_STARTED" in events or review_terminal:
            return "implementation cannot finish after review has started"
    elif event == "TEST_FEEDBACK_RECEIVED_BY_SUPERVISOR":
        if "IMPLEMENTATION_COMPLETED" not in events:
            return "test feedback requires completed implementation"
    elif event == "REVIEW_STARTED":
        if "IMPLEMENTATION_COMPLETED" not in events:
            return "review requires completed implementation"
        if implementation_terminal == {"IMPLEMENTATION_FAILED"}:
            return "review cannot start after failed implementation"
    elif event in {"REVIEW_APPROVED", "REVIEW_CHANGES_REQUESTED", "REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR"}:
        if "REVIEW_STARTED" not in events:
            return "review must start before its verdict or feedback is recorded"
        if event == "REVIEW_APPROVED" and review_terminal:
            return "review already has a terminal event for this iteration"
    elif event == "FEEDBACK_FORWARDED_TO_IMPLEMENTER":
        prior_iteration = iteration - 1
        prior_events = {
            recorded_event
            for recorded_event, recorded_iteration in history
            if recorded_iteration == prior_iteration
        }
        if iteration <= 1 or not prior_events & {
            "TEST_FEEDBACK_RECEIVED_BY_SUPERVISOR",
            "REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR",
        }:
            return "feedback can advance only from the preceding iteration"
    elif event == "ITERATION_LIMIT_REACHED" and iteration != 5:
        return "iteration limit can be reached only at iteration 5"
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
    history = _stage_event_history(trace_path)
    last_event = history[-1] if history else None
    transition_error = _stage_transition_error(history, normalized_event, iteration)
    if transition_error:
        return json.dumps({"status": "error", "error": transition_error})
    if (normalized_event, iteration) in history:
        return json.dumps(
            {"status": "already_recorded", "event": normalized_event, "iteration": iteration}
        )
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
    # Verbose mode emits one result line per test for the task test log.
    command = [python_executable, "-m", "pytest", "-v", str(test_dir)]
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
    result_trace_path = test_trace_path(task_id) if test_result_logging_enabled() else None
    if result_trace_path is not None:
        write_trace(
            result_trace_path,
            f"TEST_STARTED task={task_id} command={subprocess.list2cmdline(command)}",
        )
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
        if result_trace_path is not None:
            write_trace(result_trace_path, f"TEST_FINISHED task={task_id} status=timeout")
            if output:
                write_trace_output(result_trace_path, f"{output.rstrip()}\n")
        return json.dumps({"status": "timeout", "task_id": task_id, "command": command, "output": output})

    status = "passed" if completed.returncode == 0 else "failed"
    write_trace(trace_path, f"Tests {status} (exit code {completed.returncode})")
    if result_trace_path is not None:
        write_trace(
            result_trace_path,
            f"TEST_FINISHED task={task_id} status={status} exit_code={completed.returncode}",
        )
        if completed.stdout:
            write_trace_output(result_trace_path, f"{completed.stdout.rstrip()}\n")
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
