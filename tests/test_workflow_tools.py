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
            (test_dir / "test_sample.py").write_text(
                "def test_sample():\n    assert 1 + 1 == 2\n", encoding="utf-8"
            )
            coding_dir = test_dir.parent / "Coding"
            coding_dir.mkdir()
            (coding_dir / "sample.py").write_text(
                '"""Sample module."""\n\ndef add(left: int, right: int) -> int:\n'
                '    """Return the sum of two integers."""\n    return left + right\n',
                encoding="utf-8",
            )
            trace_path = root / "TASK-999.logs"
            trace_path.touch()
            result_trace = root / "TASK-999_test.log"
            result_trace.touch()
            completed = subprocess.CompletedProcess(
                [], 0, stdout="test_sample.py::test_addition PASSED [100%]\n1 passed\n"
            )

            environment = {
                "TASK_ID": "TASK-999",
                "TASK_DIR": "workspace/sample_task",
                "PYTHONPATH": "/launcher/src",
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(workflow_tools, "ROOT", root),
                patch.object(workflow_tools, "task_trace_path", return_value=trace_path),
                patch.object(workflow_tools, "test_result_logging_enabled", return_value=True),
                patch.object(workflow_tools, "test_trace_path", return_value=result_trace) as log_path,
                patch.object(workflow_tools.subprocess, "run", return_value=completed) as run,
            ):
                result = json.loads(workflow_tools.execute_task_tests())

            self.assertEqual(result["status"], "passed")
            command = run.call_args.args[0]
            self.assertEqual(command[:3], [str(Path(sys.executable).resolve()), "-m", "pytest"])
            self.assertEqual(command[3], "-v")
            self.assertEqual(run.call_args.kwargs["cwd"], root)
            pythonpath = run.call_args.kwargs["env"]["PYTHONPATH"].split(os.pathsep)
            self.assertEqual(pythonpath[:3], [str(root), str(root / "src"), "/launcher/src"])
            log_path.assert_called_once_with("TASK-999")
            self.assertIn(
                "test_sample.py::test_addition PASSED",
                result_trace.read_text(encoding="utf-8"),
            )

    def test_test_result_log_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            test_dir = root / "workspace" / "sample_task" / "test"
            test_dir.mkdir(parents=True)
            (test_dir / "test_sample.py").write_text(
                "def test_sample():\n    assert True\n", encoding="utf-8"
            )
            coding_dir = root / "workspace" / "sample_task" / "Coding"
            coding_dir.mkdir()
            (coding_dir / "sample.py").write_text('"""Sample module."""\n', encoding="utf-8")
            trace_path = root / "TASK-998.logs"
            trace_path.touch()
            completed = subprocess.CompletedProcess([], 0, stdout="1 passed\n")
            with (
                patch.dict(
                    os.environ,
                    {"TASK_ID": "TASK-998", "TASK_DIR": "workspace/sample_task"},
                    clear=True,
                ),
                patch.object(workflow_tools, "ROOT", root),
                patch.object(workflow_tools, "task_trace_path", return_value=trace_path),
                patch.object(workflow_tools, "test_result_logging_enabled", return_value=False),
                patch.object(workflow_tools, "test_trace_path") as log_path,
                patch.object(workflow_tools.subprocess, "run", return_value=completed),
            ):
                result = json.loads(workflow_tools.execute_task_tests())

            self.assertEqual(result["status"], "passed")
            log_path.assert_not_called()

    def test_quality_failure_blocks_a_passing_pytest_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            workspace = root / "workspace" / "sample_task"
            (workspace / "Coding").mkdir(parents=True)
            (workspace / "test").mkdir()
            (workspace / "Coding" / "sample.py").write_text(
                "def public_api():\n    return 1\n", encoding="utf-8"
            )
            (workspace / "test" / "test_sample.py").write_text(
                "def test_sample():\n    value = 1\n", encoding="utf-8"
            )
            trace = root / "TASK-997.logs"
            raw = root / "TASK-997.raw.logs"
            result_trace = root / "TASK-997_test.log"
            trace.touch()
            raw.touch()
            result_trace.touch()
            completed = subprocess.CompletedProcess([], 0, stdout="1 passed\n")
            with (
                patch.dict(os.environ, {"TASK_ID": "TASK-997", "TASK_DIR": "workspace/sample_task"}, clear=True),
                patch.object(workflow_tools, "ROOT", root),
                patch.object(workflow_tools, "task_trace_path", return_value=trace),
                patch.object(workflow_tools, "task_raw_trace_path", return_value=raw),
                patch.object(workflow_tools, "test_result_logging_enabled", return_value=True),
                patch.object(workflow_tools, "test_trace_path", return_value=result_trace),
                patch.object(workflow_tools.subprocess, "run", return_value=completed),
            ):
                result = json.loads(workflow_tools.execute_task_tests())

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["pytest_status"], "passed")
            self.assertEqual(result["quality"]["status"], "failed")
            self.assertIn("DOC-01", result_trace.read_text(encoding="utf-8"))


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


class TokenAuditTests(unittest.TestCase):
    def test_records_usage_and_full_agent_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            usage = root / "TASK-999_usage.json"
            raw = root / "TASK-999.raw.logs"
            trace = root / "TASK-999.logs"
            raw.touch()
            trace.touch()
            usage.write_text(
                json.dumps({"task_id": "TASK-999", "budget": 1000, "supervisor_snapshots": {}, "children": {}}),
                encoding="utf-8",
            )
            env = {
                "TASK_ID": "TASK-999",
                "MYCODEAGENT_SUPERVISOR_TOKEN_BUDGET": "500",
                "MYCODEAGENT_IMPLEMENTER_TOKEN_BUDGET": "400",
                "MYCODEAGENT_REVIEWER_TOKEN_BUDGET": "200",
            }
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(workflow_tools, "token_usage_path", return_value=usage),
                patch.object(workflow_tools, "task_raw_trace_path", return_value=raw),
                patch.object(workflow_tools, "task_trace_path", return_value=trace),
            ):
                token_result = json.loads(workflow_tools.record_token_usage("implementer", 1, 250))
                report_result = json.loads(workflow_tools.record_agent_report("implementer", 1, "COMPLETED", "F1: fix validation"))
            self.assertEqual(token_result["total_tokens"], 250)
            self.assertEqual(report_result["status"], "recorded")
            self.assertIn("F1: fix validation", raw.read_text(encoding="utf-8"))

    def test_persists_exhaustion_when_supervisor_exceeds_its_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            usage = root / "TASK-999_usage.json"
            trace = root / "TASK-999.logs"
            trace.touch()
            usage.write_text(
                json.dumps({"task_id": "TASK-999", "budget": 400000, "supervisor_snapshots": {}, "children": {}}),
                encoding="utf-8",
            )
            env = {
                "TASK_ID": "TASK-999",
                "MYCODEAGENT_SUPERVISOR_TOKEN_BUDGET": "75000",
                "MYCODEAGENT_IMPLEMENTER_TOKEN_BUDGET": "100000",
                "MYCODEAGENT_REVIEWER_TOKEN_BUDGET": "60000",
            }
            with (
                patch.dict(os.environ, env, clear=True),
                patch.object(workflow_tools, "token_usage_path", return_value=usage),
                patch.object(workflow_tools, "task_trace_path", return_value=trace),
            ):
                result = json.loads(workflow_tools.record_token_usage("supervisor", 2, 75908))

            ledger = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "exhausted")
            self.assertTrue(ledger["exhausted"])
            self.assertTrue(ledger["agent_exhausted"])
            self.assertFalse(ledger["task_exhausted"])
            self.assertEqual(ledger["exhausted_agents"], ["supervisor"])
            self.assertEqual(ledger["remaining_tokens"], 324092)

    def test_rejects_reviewer_finding_that_cites_an_invented_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            workspace = root / "workspace" / "sample"
            workspace.mkdir(parents=True)
            raw = root / "TASK-996.raw.logs"
            trace = root / "TASK-996.logs"
            raw.touch()
            trace.touch()
            report = """CHANGES_REQUESTED
## Review summary
- Scope: workspace/sample
- Tech stack: Python 3.11
- Tests: `pytest -v` — passed
- Code quality: inspected
- Performance: linear and bounded
- Test quality: assertions inspected
- Security: no external boundary
## Findings
- [F1] High [COR-02] — `Coding/invented.py:1` — Defect: validation is missing. Impact: invalid data executes. Evidence: file inspection. Required fix: add validation.
"""
            with (
                patch.dict(os.environ, {"TASK_ID": "TASK-996", "TASK_DIR": "workspace/sample"}, clear=True),
                patch.object(workflow_tools, "ROOT", root),
                patch.object(workflow_tools, "task_raw_trace_path", return_value=raw),
                patch.object(workflow_tools, "task_trace_path", return_value=trace),
            ):
                result = json.loads(
                    workflow_tools.record_agent_report("reviewer", 1, "CHANGES_REQUESTED", report)
            )

            self.assertEqual(result["status"], "error")
            self.assertTrue(any("does not exist" in detail for detail in result["details"]))
            self.assertEqual(raw.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
