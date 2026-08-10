"""Omnigent process construction, execution, timeouts, and cleanup."""

from __future__ import annotations

import argparse
import os
import queue
import signal
import shutil
import subprocess
import tempfile
import threading
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic

from .paths import ALLOWED_EFFORTS, ROOT, SETTINGS_PATH, WORKFLOW_PATH
from .platform_utils import repository_relative_posix, resolve_executable
from .protocol import extract_structured_report
from .tasks import TaskSpec
from .tracing import (
    debug,
    error,
    info,
    print_structured_workflow_output,
    task_raw_trace_path,
    task_trace_path,
    write_trace,
    write_trace_output,
)


@dataclass(frozen=True)
class WorkflowResult:
    """Terminal result of one Omnigent invocation."""

    exit_code: int
    report: str | None = None


def positive_timeout(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than zero")
    return parsed


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate a runner and all child processes after a timeout."""
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGTERM)
    else:  # pragma: no cover - exercised on Windows CI
        taskkill = shutil.which("taskkill")
        if taskkill is not None:
            subprocess.run(
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        elif process.poll() is None:
            process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover
            process.kill()
        process.wait()


def stream_process_output(
    command: list[str], *, environment: dict[str, str], timeout: int, trace_path: Path
) -> WorkflowResult:
    """Persist raw runner output while showing only its final structured report."""
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        command, cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        start_new_session=os.name == "posix", creationflags=creationflags,
    )
    assert process.stdout is not None
    output_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in process.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=read_output, name="mycodeagent-output-reader", daemon=True)
    reader.start()
    started_at = monotonic()
    started_at_wall = datetime.now().astimezone()
    raw_output: list[str] = []
    raw_trace_path = task_raw_trace_path(trace_path.stem)
    timed_out = False
    try:
        stream_closed = False
        while not (stream_closed and process.poll() is not None):
            remaining = timeout - (monotonic() - started_at)
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = output_queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if line is None:
                stream_closed = True
            else:
                write_trace_output(raw_trace_path, line)
                raw_output.append(line)

        if timed_out:
            terminate_process_group(process)
            ended_at = datetime.now().astimezone()
            elapsed = monotonic() - started_at
            write_trace(trace_path, f"WORKFLOW_TIMEOUT started_at={started_at_wall.isoformat()} ended_at={ended_at.isoformat()} elapsed_seconds={elapsed:.2f} limit_seconds={timeout}")
            error(f"Workflow timed out at {ended_at.isoformat(timespec='seconds')} after {elapsed:.1f}s. Trace: {trace_path}")
            return WorkflowResult(124)

        return_code = process.wait()
        report = extract_structured_report(raw_output)
        print_structured_workflow_output(report, raw_trace_path)
        ended_at = datetime.now().astimezone()
        elapsed = monotonic() - started_at
        if return_code == 0 and report is None:
            return_code = 1
            write_trace(trace_path, "WORKFLOW_PROTOCOL_ERROR reason=missing_structured_final_report")
            error("Workflow failed validation: missing required structured final report.")
        write_trace(trace_path, f"WORKFLOW_FINISHED process_exit_code={return_code} started_at={started_at_wall.isoformat()} ended_at={ended_at.isoformat()} elapsed_seconds={elapsed:.2f}")
        info(f"Workflow finished at {ended_at.isoformat(timespec='seconds')} after {elapsed:.1f}s (exit code {return_code}).")
        return WorkflowResult(return_code, report)
    finally:
        if process.poll() is None:
            terminate_process_group(process)
        reader.join(timeout=5)
        process.stdout.close()


def execute_omnigent_stage(
    prompt: str, *, target_stage: str | None = None, timeout_seconds: int | None = None,
    task: TaskSpec, todo_path: Path, delivery_approved: bool = False,
) -> WorkflowResult:
    """Render the workflow and execute one Omnigent invocation for a task."""
    with SETTINGS_PATH.open("rb") as settings_file:
        settings = tomllib.load(settings_file)
    required = ("command", "harness", "model", "effort", "time_limit_seconds")
    missing = [key for key in required if not settings.get(key)]
    if missing:
        raise SystemExit(f"Missing required runtime setting(s): {', '.join(missing)}")
    if settings["harness"] != "codex":
        raise SystemExit("workflow_runtime.toml must use the supported 'codex' harness")
    if not isinstance(settings["model"], str) or not settings["model"].strip():
        raise SystemExit("workflow_runtime.toml model must be a non-empty string")
    if settings["effort"] not in ALLOWED_EFFORTS:
        raise SystemExit(f"workflow_runtime.toml effort must be one of: {', '.join(sorted(ALLOWED_EFFORTS))}")
    timeout = int(settings["time_limit_seconds"]) if timeout_seconds is None else timeout_seconds
    if timeout <= 0:
        raise SystemExit("timeout must be greater than zero")

    trace_path = task_trace_path(task.task_id)
    environment = os.environ.copy()
    environment.update({
        "OMNIGENT_WORKFLOW_MODEL": str(settings["model"]), "OMNIGENT_WORKFLOW_EFFORT": str(settings["effort"]),
        "TASK_ID": task.task_id,
        "TASK_DIR": repository_relative_posix(task.workspace, ROOT),
        "TODO_PATH": str(todo_path.resolve()),
    })
    if delivery_approved:
        environment["MYCODEAGENT_REVIEW_STATUS"] = "APPROVED"
    rendered_workflow = WORKFLOW_PATH.read_text(encoding="utf-8").replace("${OMNIGENT_WORKFLOW_MODEL}", str(settings["model"])).replace("${OMNIGENT_WORKFLOW_EFFORT}", str(settings["effort"]))

    with tempfile.TemporaryDirectory(prefix="omnigent-workflow-") as temp_dir:
        rendered_path = Path(temp_dir) / WORKFLOW_PATH.name
        rendered_path.write_text(rendered_workflow, encoding="utf-8")
        if target_stage:
            prompt = f"STAGE ONLY: {target_stage}\nInvoke only the named workflow stage. Do not invoke, delegate to, or perform any other stage.\n\n{prompt}"
        try:
            omnigent_command = resolve_executable(str(settings["command"]))
        except RuntimeError as exc:
            write_trace(trace_path, f"WORKFLOW_LAUNCH_ERROR error={exc}")
            error(str(exc))
            return WorkflowResult(1)
        command = [omnigent_command, "run", str(rendered_path), "--harness", str(settings["harness"]), "--model", str(settings["model"]), "--no-session", "-p", prompt]
        write_trace(trace_path, f"WORKFLOW_STARTED task={task.task_id} stage={target_stage or 'full'} timeout_seconds={timeout}")
        debug(f"Trace: {trace_path}")
        info(f"Workflow started at {datetime.now().astimezone().isoformat(timespec='seconds')}")
        try:
            return stream_process_output(command, environment=environment, timeout=timeout, trace_path=trace_path)
        except OSError as exc:
            write_trace(trace_path, f"WORKFLOW_LAUNCH_ERROR error={exc}")
            error(f"Could not start workflow: {exc}")
            return WorkflowResult(1)
