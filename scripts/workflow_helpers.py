"""Workflow Helpers: Handles deterministic tasks (Changelog & PR Creation) to save LLM tokens."""

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
APPROVAL_PATH = ROOT / "git_approval.toml"
TASK_ID_PATTERN = re.compile(r"^[A-Z0-9]+-\d+$")
TASK_HEADING_PATTERN = re.compile(
    r"^##\s+(?P<task_id>[A-Z0-9]+-\d+)\s*\|\s*\w+\s*\|\s*P[0-3]\s*\|\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)


def configure_root(repository_root: str | None, approval_file: str | None) -> None:
    """Target a linked task worktree while using this current helper version."""
    global ROOT, APPROVAL_PATH
    if repository_root is not None:
        ROOT = Path(repository_root).expanduser().resolve()
        APPROVAL_PATH = ROOT / "git_approval.toml"
    if approval_file is not None:
        APPROVAL_PATH = Path(approval_file).expanduser().resolve()


def get_default_branch() -> str:
    """Resolve origin's advertised default branch with safe fallbacks."""
    symbolic = subprocess.run(
        [resolve_tool("git"), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip().startswith("origin/"):
        return symbolic.stdout.strip().split("/", 1)[1]
    for branch in ("main", "master"):
        res = subprocess.run(
            [resolve_tool("git"), "rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if res.returncode == 0:
            return branch
    raise RuntimeError("Could not resolve origin's default branch (expected origin/HEAD, main, or master)")


def resolve_tool(name: str) -> str:
    """Resolve an external command through PATH, including Windows PATHEXT."""
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"Required executable is not available on PATH: {name}")
    return resolved


def _resolved_command(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] in {"git", "gh"}:
        return [resolve_tool(cmd[0]), *cmd[1:]]
    return cmd


def run_cmd(cmd: list[str], *, allow_fail: bool = False) -> str:
    """Run a deterministic command from the repository root."""
    print(f"⚙️ Running command: {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        _resolved_command(cmd), cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 and not allow_fail:
        print(f"❌ Error running {' '.join(cmd)}:\n{result.stderr}", file=sys.stderr, flush=True)
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def normalized_repository(remote: str) -> str:
    """Normalize HTTPS/SSH GitHub remotes to host/owner/repository."""
    value = remote.strip().replace("\\", "/")
    if re.match(r"^[^/@]+@[^:]+:.+", value):
        host_part, path = value.split(":", 1)
        host = host_part.split("@", 1)[1]
    else:
        parsed = urlparse(value)
        if parsed.scheme and parsed.hostname:
            host, path = parsed.hostname, parsed.path
        else:
            return value.removesuffix(".git").strip("/").casefold()
    return f"{host}/{path.strip('/').removesuffix('.git')}".casefold()


def load_git_approval() -> dict[str, str]:
    if not APPROVAL_PATH.exists():
        raise RuntimeError(f"Missing approval configuration: {APPROVAL_PATH}")
    with APPROVAL_PATH.open("rb") as approval_file:
        approval = tomllib.load(approval_file)
    required = ("approved_git_name", "approved_git_email", "approved_github_login", "approved_remote")
    missing = [key for key in required if not isinstance(approval.get(key), str) or not approval[key]]
    if missing:
        raise RuntimeError(f"Missing approval configuration values: {', '.join(missing)}")
    return approval


def validate_task_input(task_id: str, task_dir: str) -> Path:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise RuntimeError(f"Invalid task ID: {task_id}")
    candidate = Path(task_dir.replace("\\", "/"))
    if candidate.is_absolute():
        raise RuntimeError("Task directory must be a repository-relative path")
    task_path = (ROOT / candidate).resolve()
    try:
        task_path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError("Task directory escapes the repository") from exc
    if not (task_path / "Coding").is_dir() or not (task_path / "test").is_dir():
        raise RuntimeError("Task directory must contain Coding/ and test/ directories")
    return task_path


def verify_delivery_preflight(task_id: str, task_dir: str, review_status: str) -> tuple[dict[str, str], Path]:
    if review_status != "APPROVED":
        raise RuntimeError("Pull-request delivery requires review status APPROVED")

    approval = load_git_approval()
    repository_root = Path(run_cmd(["git", "rev-parse", "--show-toplevel"])).resolve()
    if repository_root != ROOT:
        raise RuntimeError(f"Expected repository root {ROOT}, got {repository_root}")
    actual_remote = run_cmd(["git", "remote", "get-url", "origin"])
    if normalized_repository(actual_remote) != normalized_repository(approval["approved_remote"]):
        raise RuntimeError("Origin remote does not match approved_remote")
    if run_cmd(["gh", "api", "user", "--jq", ".login"]) != approval["approved_github_login"]:
        raise RuntimeError("Authenticated GitHub account does not match approved_github_login")

    return approval, validate_task_input(task_id, task_dir)


def update_changelog(task_id: str, todo_path: str = "TODO.md", changelog_path: str = "CHANGELOG.md") -> None:
    """Extracts task summary from TODO.md and appends it to CHANGELOG.md."""
    print(f"🔍 Reading {todo_path} for task {task_id}...", flush=True)
    todo_file = ROOT / todo_path
    changelog_file = ROOT / changelog_path

    if not todo_file.exists():
        print(f"❌ Error: {todo_path} does not exist.", file=sys.stderr, flush=True)
        sys.exit(1)

    task_title = None
    for line in todo_file.read_text(encoding="utf-8").splitlines():
        if task_id in line:
            match = re.search(rf"{task_id}\s*\|\s* ready\s*\|\s*\w+\s*\|\s*(.*)", line)
            if match:
                task_title = match.group(1).strip()
                break
            task_title = line.strip()

    if not task_title:
        task_title = f"Completed task {task_id}"

    changelog_content = changelog_file.read_text(encoding="utf-8") if changelog_file.exists() else "# Changelog\n\n## Unreleased\n"
    new_entry = f"- **{task_id}**: {task_title}"

    if "## Unreleased" in changelog_content:
        changelog_content = changelog_content.replace("## Unreleased\n", f"## Unreleased\n{new_entry}\n")
    else:
        changelog_content = f"## Unreleased\n{new_entry}\n\n" + changelog_content

    changelog_file.write_text(changelog_content, encoding="utf-8")
    print(f"✅ Updated {changelog_path} with: {new_entry}", flush=True)


def task_title(task_id: str, todo_path: str = "TODO.md") -> str:
    """Get a human-readable PR title from the selected task heading."""
    todo_file = ROOT / todo_path
    if not todo_file.exists():
        return f"Implement {task_id}"
    for match in TASK_HEADING_PATTERN.finditer(todo_file.read_text(encoding="utf-8")):
        if match.group("task_id") == task_id:
            title = re.sub(r"^\[[^\]]+\]\s*", "", match.group("title").strip())
            return title.replace("`", "")[:180]
    return f"Implement {task_id}"


def create_pull_request(task_id: str, task_dir: str, review_status: str) -> None:
    """Stages specific task directory, commits, pushes branch, and creates PR."""
    print(f"🚀 Initializing PR process for Task ID: {task_id} in directory: {task_dir}...", flush=True)
    approval, task_path = verify_delivery_preflight(task_id, task_dir, review_status)
    branch_name = f"feature/{task_id.lower()}"

    run_cmd(["git", "fetch", "--prune", "origin"])
    base_branch = get_default_branch()
    print(f"🎯 Target base branch resolved to: {base_branch}", flush=True)

    run_cmd(["git", "config", "user.name", approval["approved_git_name"]])
    run_cmd(["git", "config", "user.email", approval["approved_git_email"]])
    current_branch = run_cmd(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], allow_fail=True)
    if not current_branch:
        raise RuntimeError("Delivery requires an attached Git branch; detached HEAD is not supported")
    if current_branch != branch_name:
        existing_branch = subprocess.run(
            [resolve_tool("git"), "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=ROOT, check=False,
        ).returncode == 0
        if existing_branch:
            raise RuntimeError(
                f"Refusing to switch from {current_branch} to existing {branch_name}; "
                "use an isolated worktree or switch branches manually after preserving the task workspace"
            )
        run_cmd(["git", "switch", "-c", branch_name])
        validate_task_input(task_id, task_dir)

    remote_branch = subprocess.run(
        [resolve_tool("git"), "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch_name}"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if remote_branch.returncode == 0:
        run_cmd(["git", "fetch", "origin", f"+refs/heads/{branch_name}:refs/remotes/origin/{branch_name}"])
        contains_remote = subprocess.run(
            [resolve_tool("git"), "merge-base", "--is-ancestor", f"origin/{branch_name}", branch_name],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0
        if not contains_remote:
            raise RuntimeError(
                f"Remote branch origin/{branch_name} is not an ancestor of {branch_name}; "
                "reconcile the branch histories before delivery"
            )
    elif remote_branch.returncode not in {2}:
        raise RuntimeError(f"Could not inspect remote branch origin/{branch_name}")

    task_relative = task_path.relative_to(ROOT).as_posix()
    run_cmd(["git", "add", f"{task_relative}/Coding/", f"{task_relative}/test/", "CHANGELOG.md"])

    res = subprocess.run(
        [resolve_tool("git"), "diff", "--cached", "--quiet"], cwd=ROOT, check=False,
    )
    if res.returncode != 0:
        run_cmd(["git", "commit", "-m", f"feat({task_id}): implement task solution and tests"])
    else:
        print("ℹ️ No new staged changes to commit; proceeding to push.", flush=True)

    run_cmd(["git", "push", "-u", "origin", branch_name])

    print("🐙 Creating Pull Request on GitHub...", flush=True)
    title = f"feat({task_id}): {task_title(task_id)}"
    pr_url = run_cmd([
        "gh", "pr", "create",
        "--base", base_branch,
        "--head", branch_name,
        "--title", title,
        "--body", f"Automated PR generated for task `{task_id}` inside isolated directory `{task_dir}/`."
    ])

    print(f"\n✅ Pull Request Created Successfully!\n🔗 {pr_url}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workflow Helper Utility")
    parser.add_argument("--repo-root", help="Repository or linked worktree to operate in")
    parser.add_argument("--approval-file", help="Approved Git policy file to use for delivery preflight")
    parser.add_argument("action", choices=["changelog", "pr"], help="Action to execute")
    parser.add_argument("--task-id", required=True, help="Task identifier (e.g., SWAF-045)")
    parser.add_argument("--task-dir", default="", help="Task directory path (e.g., workspace/fibonacci)")
    parser.add_argument("--review-status", default="", help="Required APPROVED review status for PR delivery")

    args = parser.parse_args()
    configure_root(args.repo_root, args.approval_file)

    if args.action == "changelog":
        update_changelog(args.task_id)
    elif args.action == "pr":
        if not args.task_dir:
            print("❌ Error: --task-dir is required when action is 'pr'.", file=sys.stderr, flush=True)
            sys.exit(1)
        try:
            create_pull_request(args.task_id, args.task_dir, args.review_status)
        except RuntimeError as exc:
            print(f"❌ Delivery preflight failed: {exc}", file=sys.stderr, flush=True)
            sys.exit(1)
