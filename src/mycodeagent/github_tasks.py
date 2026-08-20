"""Read eligible GitHub Project issues and normalize them as local work orders."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import TRACE_DIR
from .platform_utils import resolve_executable
from .tasks import TITLE_WORKSPACE, parse_todo_file


@dataclass(frozen=True)
class GitHubIssue:
    number: int
    repository: str
    title: str
    body: str
    state: str
    labels: tuple[str, ...]
    url: str


def _run_gh(arguments: list[str]) -> dict[str, object]:
    """Run one read-only GitHub CLI query and decode its JSON response."""
    gh = resolve_executable("gh")
    completed = subprocess.run(
        [gh, *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "GitHub CLI query failed"
        raise RuntimeError(detail)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub CLI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub CLI returned an unexpected JSON response")
    return payload


def _todo_issue_references(owner: str, project_number: int) -> list[tuple[str, int]]:
    """Return linked issue references whose GitHub Project status is Todo."""
    payload = _run_gh(
        [
            "project",
            "item-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
            "--limit",
            "100",
        ]
    )
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise RuntimeError("GitHub Project response does not contain an items list")
    references: list[tuple[str, int]] = []
    for item in items:
        if not isinstance(item, dict) or str(item.get("status", "")).casefold() != "todo":
            continue
        content = item.get("content")
        if not isinstance(content, dict) or str(content.get("type", "")).casefold() != "issue":
            continue
        repository = str(content.get("repository", item.get("repository", ""))).strip()
        number = content.get("number")
        if repository and isinstance(number, int) and number > 0:
            references.append((repository, number))
    return references


def _fetch_issue(repository: str, number: int) -> GitHubIssue:
    payload = _run_gh(
        [
            "issue",
            "view",
            str(number),
            "--repo",
            repository,
            "--json",
            "number,title,body,state,labels,url",
        ]
    )
    labels_value = payload.get("labels", [])
    labels = tuple(
        str(label.get("name", "")).strip()
        for label in labels_value
        if isinstance(label, dict) and str(label.get("name", "")).strip()
    ) if isinstance(labels_value, list) else ()
    return GitHubIssue(
        number=int(payload.get("number", number)),
        repository=repository,
        title=str(payload.get("title", "")).strip(),
        body=str(payload.get("body", "")).strip(),
        state=str(payload.get("state", "")).upper(),
        labels=labels,
        url=str(payload.get("url", "")).strip(),
    )


def _priority(labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.fullmatch(r"P([0-3])", label.strip(), flags=re.IGNORECASE)
        if match:
            return f"P{match.group(1)}"
    return "P2"


def _work_order_path(issue: GitHubIssue) -> Path:
    repository_slug = issue.repository.replace("/", "-").lower()
    return TRACE_DIR / "work-orders" / f"{repository_slug}-issue-{issue.number}.md"


def _is_locally_blocked(path: Path) -> bool:
    """Prevent concurrent or duplicate delivered runs while permitting retries."""
    if not path.is_file():
        return False
    tasks = parse_todo_file(path)
    return any(info["state"] in {"working", "delivered"} for info in tasks.values())


def _write_work_order(issue: GitHubIssue) -> tuple[Path, str]:
    """Create a TODO-compatible, single-issue work order."""
    task_id = f"ISSUE-{issue.number}"
    title = issue.title or f"GitHub issue #{issue.number}"
    workspace_match = TITLE_WORKSPACE.search(f"{title}\n{issue.body}")
    if workspace_match is not None and TITLE_WORKSPACE.search(title) is None:
        workspace = workspace_match.group(1).replace("\\", "/").rstrip("/")
        title = f"{title} in `{workspace}/`"
    body = issue.body or "No issue description was provided."
    work_order = (
        f"## {task_id} | ready | {_priority(issue.labels)} | [GITHUB] {title}\n"
        f"- GitHub Issue: {issue.url}\n"
        f"- Repository: {issue.repository}\n"
        f"\n{body}\n"
    )
    path = _work_order_path(issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(work_order, encoding="utf-8")
    return path, task_id


def select_github_project_task(owner: str, project_number: int) -> tuple[Path, str]:
    """Select the first unprocessed Todo item backed by an open GitHub issue."""
    for repository, number in _todo_issue_references(owner, project_number):
        issue = _fetch_issue(repository, number)
        if issue.state != "OPEN":
            continue
        path = _work_order_path(issue)
        if _is_locally_blocked(path):
            continue
        return _write_work_order(issue)
    raise RuntimeError(
        f"No unprocessed OPEN issue with project status Todo was found in {owner} project {project_number}."
    )
