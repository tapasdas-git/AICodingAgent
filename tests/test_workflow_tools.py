import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycodeagent import workflow_tools


class ExecuteTaskTestsEnvironmentTests(unittest.TestCase):
    def test_uses_python_module_and_exposes_worktree_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            test_dir = root / "workspace" / "sample_task" / "test"
            test_dir.mkdir(parents=True)
            trace_path = root / "TASK-999.logs"
            trace_path.touch()
            completed = subprocess.CompletedProcess([], 0, stdout="1 passed\n")

            environment = {
                "TASK_ID": "TASK-999",
                "TASK_DIR": "workspace/sample_task",
                "PYTHONPATH": "/launcher/src",
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(workflow_tools, "ROOT", root),
                patch.object(workflow_tools, "task_trace_path", return_value=trace_path),
                patch.object(workflow_tools.subprocess, "run", return_value=completed) as run,
            ):
                result = json.loads(workflow_tools.execute_task_tests())

            self.assertEqual(result["status"], "passed")
            command = run.call_args.args[0]
            self.assertEqual(command[:3], [str(Path(sys.executable).resolve()), "-m", "pytest"])
            self.assertEqual(run.call_args.kwargs["cwd"], root)
            pythonpath = run.call_args.kwargs["env"]["PYTHONPATH"].split(os.pathsep)
            self.assertEqual(pythonpath[:3], [str(root), str(root / "src"), "/launcher/src"])


class RecordStageEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trace_path = Path(self.temp_dir.name) / "TASK-132.logs"
        self.trace_path.touch()
        self.environment = patch.dict(os.environ, {"TASK_ID": "TASK-132"}, clear=True)
        self.trace_patch = patch.object(
            workflow_tools, "task_trace_path", return_value=self.trace_path
        )
        self.environment.start()
        self.trace_patch.start()

    def tearDown(self) -> None:
        self.trace_patch.stop()
        self.environment.stop()
        self.temp_dir.cleanup()

    def record(self, event: str, iteration: int) -> dict[str, object]:
        return json.loads(workflow_tools.record_stage_event(event, iteration))

    def test_duplicate_event_is_idempotent(self) -> None:
        self.assertEqual(self.record("IMPLEMENTATION_STARTED", 1)["status"], "recorded")
        self.assertEqual(self.record("IMPLEMENTATION_STARTED", 1)["status"], "already_recorded")
        self.assertEqual(
            self.trace_path.read_text(encoding="utf-8").count("Implementation started (iteration 1)"),
            1,
        )

    def test_rejects_stale_iteration_after_remediation_begins(self) -> None:
        self.record("IMPLEMENTATION_STARTED", 1)
        self.record("IMPLEMENTATION_COMPLETED", 1)
        self.record("REVIEW_STARTED", 1)
        self.record("REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR", 1)
        self.record("FEEDBACK_FORWARDED_TO_IMPLEMENTER", 2)

        result = self.record("IMPLEMENTATION_COMPLETED", 1)

        self.assertEqual(result["status"], "error")
        self.assertIn("current iteration is 2", str(result["error"]))

    def test_task_132_replay_does_not_corrupt_final_review(self) -> None:
        self.record("IMPLEMENTATION_STARTED", 1)
        self.record("IMPLEMENTATION_COMPLETED", 1)
        self.record("REVIEW_STARTED", 1)
        self.record("REVIEW_FEEDBACK_RECEIVED_BY_SUPERVISOR", 1)
        self.record("FEEDBACK_FORWARDED_TO_IMPLEMENTER", 2)
        self.record("IMPLEMENTATION_COMPLETED", 2)
        self.record("REVIEW_STARTED", 2)

        stale = self.record("IMPLEMENTATION_COMPLETED", 1)
        duplicate = self.record("IMPLEMENTATION_COMPLETED", 2)
        approved = self.record("REVIEW_APPROVED", 2)

        self.assertEqual(stale["status"], "error")
        self.assertEqual(duplicate["status"], "already_recorded")
        self.assertEqual(approved["status"], "recorded")
        trace = self.trace_path.read_text(encoding="utf-8")
        self.assertEqual(trace.count("Implementation completed (iteration 1)"), 1)
        self.assertEqual(trace.count("Remediation completed (iteration 2)"), 1)
        self.assertTrue(trace.rstrip().endswith("Review approved (iteration 2)"))

    def test_rejects_review_before_completed_implementation(self) -> None:
        self.record("IMPLEMENTATION_STARTED", 1)

        result = self.record("REVIEW_STARTED", 1)

        self.assertEqual(result["status"], "error")
        self.assertIn("completed implementation", str(result["error"]))

    def test_new_workflow_ignores_events_from_an_earlier_run(self) -> None:
        self.trace_path.write_text(
            "[time] WORKFLOW_STARTED task=TASK-132 stage=full timeout_seconds=1800\n"
            "[time] Implementation started (iteration 1)\n"
            "[time] Implementation completed (iteration 1)\n"
            "[time] Review started (iteration 1)\n"
            "[time] Review failed: changes requested (iteration 1)\n"
            "[time] Orchestrator received review feedback (iteration 1)\n"
            "[time] Orchestrator forwarded feedback for remediation (iteration 2)\n"
            "[time] Remediation started by supervisor (iteration 2)\n"
            "[time] Remediation completed (iteration 2)\n"
            "[time] Review started (iteration 2)\n"
            "[time] Review approved (iteration 2)\n"
            "[time] WORKFLOW_FINISHED process_exit_code=0\n"
            "[time] WORKFLOW_STARTED task=TASK-132 stage=full timeout_seconds=1800\n",
            encoding="utf-8",
        )

        result = self.record("IMPLEMENTATION_STARTED", 1)

        self.assertEqual(result["status"], "recorded")


if __name__ == "__main__":
    unittest.main()
