import unittest
from unittest.mock import patch

from scripts import workflow_helpers


class EnsurePullRequestTests(unittest.TestCase):
    def test_returns_existing_pull_request_without_creating_duplicate(self) -> None:
        with (
            patch.object(
                workflow_helpers,
                "find_existing_pull_request",
                return_value="https://github.com/example/repo/pull/3",
            ),
            patch.object(workflow_helpers, "run_cmd") as run_cmd,
        ):
            result = workflow_helpers.ensure_pull_request(
                "TASK-134", "workspace/config_loader", "feature/task-134", "main"
            )

        self.assertEqual(result, "https://github.com/example/repo/pull/3")
        run_cmd.assert_not_called()

    def test_returns_url_from_successful_creation(self) -> None:
        with (
            patch.object(workflow_helpers, "find_existing_pull_request", return_value=None),
            patch.object(
                workflow_helpers,
                "run_cmd",
                return_value="https://github.com/example/repo/pull/4",
            ),
        ):
            result = workflow_helpers.ensure_pull_request(
                "TASK-135", "workspace/config_loader", "feature/task-135", "main"
            )

        self.assertEqual(result, "https://github.com/example/repo/pull/4")

    def test_reconciles_pr_created_despite_client_timeout(self) -> None:
        with (
            patch.object(
                workflow_helpers,
                "find_existing_pull_request",
                side_effect=[None, "https://github.com/example/repo/pull/5"],
            ) as find_pr,
            patch.object(
                workflow_helpers,
                "run_cmd",
                side_effect=RuntimeError("gh pr create timed out"),
            ),
        ):
            result = workflow_helpers.ensure_pull_request(
                "TASK-136", "workspace/config_loader", "feature/task-136", "main"
            )

        self.assertEqual(result, "https://github.com/example/repo/pull/5")
        self.assertEqual(find_pr.call_count, 2)

    def test_preserves_failure_when_reconciliation_finds_no_pr(self) -> None:
        with (
            patch.object(
                workflow_helpers,
                "find_existing_pull_request",
                side_effect=[None, None],
            ),
            patch.object(
                workflow_helpers,
                "run_cmd",
                side_effect=RuntimeError("gh pr create failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "gh pr create failed"):
                workflow_helpers.ensure_pull_request(
                    "TASK-137", "workspace/config_loader", "feature/task-137", "main"
                )


if __name__ == "__main__":
    unittest.main()
