import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycodeagent import github_tasks
from mycodeagent.__main__ import build_parser


class GitHubTaskSelectionTests(unittest.TestCase):
    def test_selects_open_todo_issue_and_builds_ready_work_order(self) -> None:
        project_payload = {
            "items": [
                {
                    "status": "Todo",
                    "content": {
                        "type": "Issue",
                        "repository": "tapasdas-git/AICodingAgent",
                        "number": 23,
                    },
                }
            ]
        }
        issue_payload = {
            "number": 23,
            "title": "Build Modular Calculator Engine",
            "body": "Build it in workspace/calculator/\nOutcome: Add arithmetic operations.",
            "state": "OPEN",
            "labels": [{"name": "P1"}],
            "url": "https://github.com/tapasdas-git/AICodingAgent/issues/23",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(github_tasks, "TRACE_DIR", Path(temp_dir)),
                patch.object(
                    github_tasks, "_run_gh", side_effect=[project_payload, issue_payload]
                ),
            ):
                path, task_id = github_tasks.select_github_project_task("tapasdas-git", 4)
                content = path.read_text(encoding="utf-8")

        self.assertEqual(task_id, "ISSUE-23")
        self.assertIn("## ISSUE-23 | ready | P1 |", content)
        self.assertIn("`workspace/calculator/`", content)
        self.assertIn("GitHub Issue:", content)

    def test_skips_closed_issue_and_non_todo_items(self) -> None:
        project_payload = {
            "items": [
                {
                    "status": "Done",
                    "content": {
                        "type": "Issue",
                        "repository": "owner/repo",
                        "number": 1,
                    },
                },
                {
                    "status": "Todo",
                    "content": {
                        "type": "Issue",
                        "repository": "owner/repo",
                        "number": 2,
                    },
                },
            ]
        }
        closed_issue = {
            "number": 2,
            "title": "Closed task",
            "body": "No longer actionable",
            "state": "CLOSED",
            "labels": [],
            "url": "https://github.com/owner/repo/issues/2",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(github_tasks, "TRACE_DIR", Path(temp_dir)),
                patch.object(
                    github_tasks, "_run_gh", side_effect=[project_payload, closed_issue]
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "No unprocessed OPEN issue"):
                    github_tasks.select_github_project_task("owner", 4)

    def test_does_not_reselect_locally_delivered_issue(self) -> None:
        project_payload = {
            "items": [
                {
                    "status": "Todo",
                    "content": {
                        "type": "Issue",
                        "repository": "owner/repo",
                        "number": 9,
                    },
                }
            ]
        }
        issue_payload = {
            "number": 9,
            "title": "Completed locally",
            "body": "Outcome: done",
            "state": "OPEN",
            "labels": [],
            "url": "https://github.com/owner/repo/issues/9",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_dir = Path(temp_dir)
            work_order = trace_dir / "work-orders" / "owner-repo-issue-9.md"
            work_order.parent.mkdir(parents=True)
            work_order.write_text(
                "## ISSUE-9 | delivered | P2 | Completed locally\n", encoding="utf-8"
            )
            with (
                patch.object(github_tasks, "TRACE_DIR", trace_dir),
                patch.object(
                    github_tasks, "_run_gh", side_effect=[project_payload, issue_payload]
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "No unprocessed OPEN issue"):
                    github_tasks.select_github_project_task("owner", 4)

    def test_reselects_reviewed_issue_for_delivery_retry(self) -> None:
        project_payload = {
            "items": [
                {
                    "status": "Todo",
                    "content": {
                        "type": "Issue",
                        "repository": "owner/repo",
                        "number": 10,
                    },
                }
            ]
        }
        issue_payload = {
            "number": 10,
            "title": "Retry delivery",
            "body": "Outcome: deliver the task",
            "state": "OPEN",
            "labels": [],
            "url": "https://github.com/owner/repo/issues/10",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_dir = Path(temp_dir)
            work_order = trace_dir / "work-orders" / "owner-repo-issue-10.md"
            work_order.parent.mkdir(parents=True)
            work_order.write_text(
                "## ISSUE-10 | reviewed | P2 | Retry delivery\n", encoding="utf-8"
            )
            with (
                patch.object(github_tasks, "TRACE_DIR", trace_dir),
                patch.object(
                    github_tasks, "_run_gh", side_effect=[project_payload, issue_payload]
                ),
            ):
                selected_path, task_id = github_tasks.select_github_project_task("owner", 4)

            self.assertEqual(task_id, "ISSUE-10")
            self.assertIn("| ready |", selected_path.read_text(encoding="utf-8"))

    def test_github_submit_parser_is_separate_from_submit(self) -> None:
        args = build_parser().parse_args(
            ["github-submit", "--owner", "tapasdas-git", "--project", "4", "--mode", "2"]
        )

        self.assertEqual(args.command, "github-submit")
        self.assertEqual(args.owner, "tapasdas-git")
        self.assertEqual(args.project, 4)


if __name__ == "__main__":
    unittest.main()
