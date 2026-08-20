"""Private task traces and concise terminal report rendering."""

from __future__ import annotations

import re
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from .paths import SETTINGS_PATH, TRACE_DIR
from .platform_utils import restrict_file_permissions

SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:[A-Za-z0-9]+_)?(?:api[_-]?key|secret|password|token)\b\s*(?:=|:)\s*)([^\s,;]+)"
)
LOG_LEVELS = {"debug", "info", "error"}


def test_result_logging_enabled() -> bool:
    """Return whether full deterministic test output should be persisted."""
    try:
        with SETTINGS_PATH.open("rb") as settings_file:
            configured = tomllib.load(settings_file).get("test_result_logging_enabled", True)
        return configured if isinstance(configured, bool) else True
    except (OSError, tomllib.TOMLDecodeError):
        return True


def configured_console_log_levels() -> set[str]:
    """Read enabled console levels; remain verbose if configuration is invalid."""
    try:
        with SETTINGS_PATH.open("rb") as settings_file:
            configured = tomllib.load(settings_file).get("console_log_levels", list(LOG_LEVELS))
        if not isinstance(configured, list):
            return set(LOG_LEVELS)
        levels = {str(level).lower() for level in configured}
        return levels if levels <= LOG_LEVELS else set(LOG_LEVELS)
    except (OSError, tomllib.TOMLDecodeError):
        return set(LOG_LEVELS)


def log(level: str, message: str) -> None:
    """Print a redacted console message when its configured level is enabled."""
    normalized = level.lower()
    if normalized not in LOG_LEVELS:
        raise ValueError(f"Unknown log level: {level}")
    if normalized not in configured_console_log_levels():
        return
    stream = sys.stderr if normalized == "error" else sys.stdout
    print(f"[{normalized.upper()}] {redact_secrets(message)}", file=stream)


def debug(message: str) -> None:
    log("debug", message)


def info(message: str) -> None:
    log("info", message)


def error(message: str) -> None:
    log("error", message)


def redact_secrets(message: str) -> str:
    return SECRET_PATTERN.sub(r"\1[REDACTED]", message)


def task_trace_path(task_id: str) -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"{task_id}.logs"
    trace_path.touch(exist_ok=True)
    restrict_file_permissions(trace_path)
    return trace_path


def task_raw_trace_path(task_id: str) -> Path:
    """Return the verbose diagnostic log kept separate from the live timeline."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"{task_id}.raw.logs"
    trace_path.touch(exist_ok=True)
    restrict_file_permissions(trace_path)
    return trace_path


def test_trace_path(task_id: str) -> Path:
    """Return the task-specific append-only log for deterministic test results."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"{task_id}_test.log"
    trace_path.touch(exist_ok=True)
    restrict_file_permissions(trace_path)
    return trace_path


def token_usage_path(task_id: str) -> Path:
    """Return the deterministic task-level token usage ledger path."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    usage_path = TRACE_DIR / f"{task_id}_usage.json"
    usage_path.touch(exist_ok=True)
    restrict_file_permissions(usage_path)
    return usage_path


def write_trace(trace_path: Path, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with trace_path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(f"[{timestamp}] {redact_secrets(message)}\n")


def write_trace_output(trace_path: Path, line: str) -> None:
    with trace_path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(redact_secrets(line))


def print_structured_workflow_output(report: str | None, trace_path: Path) -> None:
    """Render a protocol result without deciding workflow success or failure."""
    if report is not None:
        print(f"\n{report}")
        return
    error("The agent did not return the required structured final report.")
    info(f"Full raw output: {trace_path}")
