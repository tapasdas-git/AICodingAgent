import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mycodeagent.protocol import extract_structured_report
from mycodeagent.tracing import (
    error,
    info,
    print_structured_workflow_output,
    test_result_logging_enabled as is_test_result_logging_enabled,
)


class StructuredWorkflowOutputTests(unittest.TestCase):
    def test_test_result_logging_can_be_disabled_in_runtime_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "workflow_runtime.toml"
            settings_path.write_text("test_result_logging_enabled = false\n", encoding="utf-8")
            with patch("mycodeagent.tracing.SETTINGS_PATH", settings_path):
                self.assertFalse(is_test_result_logging_enabled())

    def test_test_result_logging_defaults_to_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.toml"
            with patch("mycodeagent.tracing.SETTINGS_PATH", missing_path):
                self.assertTrue(is_test_result_logging_enabled())

    def test_extracts_task_report_without_newline_before_heading(self) -> None:
        report = """# Task workflow: TASK-109
## Outcome
- Status: verification complete
- Final review: APPROVED
## Execution summary
- Implementation: completed
## Next action
- None"""
        output = io.StringIO()

        result = extract_structured_report(["The final review is approved.", report])
        with tempfile.TemporaryDirectory() as temp_dir, redirect_stdout(output):
            print_structured_workflow_output(result, Path(temp_dir) / "raw.log")

        self.assertEqual(result, report)
        self.assertIn(report, output.getvalue())

    def test_rejects_incomplete_task_report(self) -> None:
        output = io.StringIO()

        result = extract_structured_report(
            ["progress# Task workflow: TASK-109\n## Outcome\n- Status: failed"]
        )
        with tempfile.TemporaryDirectory() as temp_dir, redirect_stderr(output):
            with patch("mycodeagent.tracing.configured_console_log_levels", return_value={"error"}):
                print_structured_workflow_output(result, Path(temp_dir) / "raw.log")

        self.assertIsNone(result)
        self.assertIn(
            "did not return the required structured final report", output.getvalue()
        )

    def test_console_levels_can_be_selected_independently(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("mycodeagent.tracing.configured_console_log_levels", return_value={"error"}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                info("hidden information")
                error("visible failure")

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("[ERROR] visible failure", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
