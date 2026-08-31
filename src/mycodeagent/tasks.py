"""TODO.md parsing, workspace validation, and task state updates."""

from __future__ import annotations

import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import ROOT
from .file_lock import task_state_lock
from .platform_utils import repository_relative_posix

TASK_HEADING = re.compile(
    r"^##\s+([A-Z0-9]+-\d+)\s*\|\s*(\w+)\s*\|\s*(P[0-3])\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
TITLE_WORKSPACE = re.compile(r"`?(workspace[\\/][A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*[\\/]?)`?")
REQUIRED_TASK_SECTIONS = (
    "Outcome",
    "Context",
    "Workspace",
    "Technology Stack",
    "Public API",
    "Functional Requirements",
    "Input Validation",
    "Error Behavior",
    "Performance and Operational Requirements",
    "Security Requirements",
    "Edge Cases",
    "Acceptance Criteria",
    "Out of Scope",
)
PLACEHOLDER_TEXT = re.compile(
    r"(?:<[^>]+>|\b(?:tbd|todo|to be decided|fill this|placeholder)\b)",
    re.IGNORECASE,
)


class TaskReadinessError(ValueError):
    """A ready task does not satisfy the strict implementation template."""


@dataclass(frozen=True)
class TaskSpec:
    """The safe, resolved execution scope for one TODO task."""

    task_id: str
    state: str
    priority: str
    title: str
    workspace: Path


def _task_body_sections(section: str) -> dict[str, str]:
    """Return third-level task sections keyed case-insensitively by heading."""
    heading = re.compile(r"^#{3,6}\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading.finditer(section))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        result[match.group(1).strip().casefold()] = section[match.end() : end].strip()
    return result


def validate_task_readiness(todo_path: Path, task_id: str) -> None:
    """Reject a ready task that does not follow ``TASK_TEMPLATE.md``."""
    content = todo_path.read_text(encoding="utf-8")
    matches = list(TASK_HEADING.finditer(content))
    for index, match in enumerate(matches):
        if match.group(1) != task_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section = content[match.end() : end]
        sections = _task_body_sections(section)
        missing = [name for name in REQUIRED_TASK_SECTIONS if not sections.get(name.casefold())]
        placeholders = [
            name for name in REQUIRED_TASK_SECTIONS
            if sections.get(name.casefold()) and PLACEHOLDER_TEXT.search(sections[name.casefold()])
        ]
        workspace = sections.get("workspace", "")
        missing_paths = [
            label for label in ("Source", "Tests", "Requirements")
            if re.search(rf"^\s*-\s*{label}:\s*`?[^`\n]+`?\s*$", workspace, re.MULTILINE) is None
        ]
        problems = []
        if missing:
            problems.append("missing or empty sections: " + ", ".join(missing))
        if placeholders:
            problems.append("unresolved placeholders in: " + ", ".join(placeholders))
        if missing_paths:
            problems.append("Workspace is missing paths: " + ", ".join(missing_paths))
        if problems:
            raise TaskReadinessError(
                f"Task {task_id} is not implementation-ready; " + "; ".join(problems)
                + ". Complete TASK_TEMPLATE.md and mark the task ready again."
            )
        return
    raise ValueError(f"Task ID '{task_id}' not found in {todo_path.name}")


def parse_todo_file(todo_path: Path) -> dict[str, dict[str, str]]:
    """Parse TODO.md and return task metadata in document order."""
    if not todo_path.exists():
        print(f"Error: Could not find {todo_path}", file=sys.stderr)
        raise SystemExit(1)

    tasks: dict[str, dict[str, str]] = {}
    for match in TASK_HEADING.finditer(todo_path.read_text(encoding="utf-8")):
        task_id, state, priority, title = match.groups()
        if task_id in tasks:
            raise ValueError(f"Duplicate task ID in {todo_path}: {task_id}")
        tasks[task_id] = {"state": state.lower(), "priority": priority, "title": title}
    return tasks


def _resolve_workspace(task_id: str, title: str, section: str) -> Path:
    """Resolve an explicit workspace or derive a safe one from minimal metadata."""
    source_match = re.search(r"^\s*-\s*Source:\s*`?([^`\n]+)`?\s*$", section, re.MULTILINE)
    title_match = TITLE_WORKSPACE.search(title)
    if source_match is not None:
        source_value = source_match.group(1).strip().replace("\\", "/")
    elif title_match is not None:
        source_value = title_match.group(1).replace("\\", "/").rstrip("/")
    else:
        source_value = f"workspace/{task_id.lower().replace('-', '_')}"

    source_path = (ROOT / source_value).resolve()
    try:
        source_path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"Task {task_id} source path escapes the repository: {source_value}") from exc

    workspace = source_path.parent if source_path.name.lower() == "coding" else source_path
    if workspace == ROOT:
        raise ValueError(f"Task {task_id} workspace cannot be the repository root")
    return workspace


def get_task_spec(todo_path: Path, task_id: str) -> TaskSpec:
    """Read a task and derive omitted workspace details safely."""
    content = todo_path.read_text(encoding="utf-8")
    matches = list(TASK_HEADING.finditer(content))
    for index, match in enumerate(matches):
        parsed_id, state, priority, title = match.groups()
        if parsed_id != task_id:
            continue

        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section = content[match.end() : section_end]
        if state.lower() == "ready":
            validate_task_readiness(todo_path, task_id)
        workspace = _resolve_workspace(task_id, title, section)

        declared_paths = {
            "Tests": workspace / "test",
            "Requirements": workspace / "Coding" / "requirements.txt",
        }
        for label, expected_path in declared_paths.items():
            declared_match = re.search(
                rf"^\s*-\s*{label}:\s*`?([^`\n]+)`?\s*$", section, re.MULTILINE
            )
            if declared_match is None:
                continue
            declared_path = (ROOT / declared_match.group(1).strip().replace("\\", "/")).resolve()
            if declared_path != expected_path.resolve():
                raise ValueError(
                    f"Task {task_id} has inconsistent {label} path: "
                    f"expected {expected_path.relative_to(ROOT)}, got "
                    f"{declared_match.group(1).strip()}"
                )
        return TaskSpec(task_id, state.lower(), priority, title, workspace)

    raise ValueError(f"Task ID '{task_id}' not found in {todo_path.name}")


def get_task_section(todo_path: Path, task_id: str) -> str:
    """Return a task section enriched with safely derived workspace details."""
    content = todo_path.read_text(encoding="utf-8")
    matches = list(TASK_HEADING.finditer(content))
    for index, match in enumerate(matches):
        if match.group(1) == task_id:
            section_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            raw_section = content[match.start() : section_end].strip()
            body = content[match.end() : section_end]
            spec = get_task_spec(todo_path, task_id)
            workspace = repository_relative_posix(spec.workspace, ROOT)
            derived = []
            if re.search(r"^\s*-\s*Source:", body, re.MULTILINE) is None:
                derived.append(f"- Source: `{workspace}/Coding/`")
            if re.search(r"^\s*-\s*Tests:", body, re.MULTILINE) is None:
                derived.append(f"- Tests: `{workspace}/test/`")
            if re.search(r"^\s*-\s*Requirements:", body, re.MULTILINE) is None:
                derived.append(f"- Requirements: `{workspace}/Coding/requirements.txt`")
            if derived:
                raw_section += "\n\n<!-- Derived by MyCodeAgent; TODO metadata was omitted. -->\n" + "\n".join(derived)
            return raw_section + "\n"
    raise ValueError(f"Task ID '{task_id}' not found in {todo_path.name}")


def get_first_ready_task(tasks: dict[str, dict[str, str]]) -> str | None:
    """Find the first task marked with state ``ready``."""
    return next((task_id for task_id, info in tasks.items() if info["state"] == "ready"), None)


def update_task_state(
    todo_path: Path,
    task_id: str,
    new_state: str,
    *,
    expected_state: str | None = None,
) -> bool:
    """Atomically change one task state, optionally guarding its prior state."""
    with task_state_lock(todo_path):
        content = todo_path.read_text(encoding="utf-8")
        heading = re.compile(
            rf"^(##\s+{re.escape(task_id)}\s*\|\s*)(\w+)(\s*\|\s*P[0-3]\s*\|.*)$",
            re.MULTILINE | re.IGNORECASE,
        )

        def replace(match: re.Match[str]) -> str:
            if expected_state is not None and match.group(2).lower() != expected_state.lower():
                return match.group(0)
            return f"{match.group(1)}{new_state}{match.group(3)}"

        updated, replacements = heading.subn(replace, content, count=1)
        if replacements != 1 or updated == content:
            return False
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=todo_path.parent, delete=False) as temp_file:
            temp_file.write(updated)
            temporary_path = Path(temp_file.name)
        for attempt in range(3):
            try:
                temporary_path.replace(todo_path)
                return True
            except PermissionError:
                if attempt == 2:
                    temporary_path.unlink(missing_ok=True)
                    raise
                time.sleep(0.05 * (attempt + 1))
    return False
