import contextlib
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from mycodeagent.runner import (
    sleep_preventing_command,
    stream_process_output,
    suspension_gap_seconds,
    workflow_environment,
)


REPORT = """# Task workflow: TASK-999
## Outcome
- Status: verification complete
- Final review: APPROVED
## Execution summary
- Implementation: completed
## Next action
- None
"""


class RunnerStreamingTests(unittest.TestCase):
    def test_workflow_environment_exposes_src_layout_to_omnigent(self) -> None:
        with patch("mycodeagent.runner.ROOT", Path("/repo")):
            environment = workflow_environment({"PYTHONPATH": "/existing"})

        self.assertEqual(
            environment["PYTHONPATH"].split(os.pathsep),
            ["/repo/src", "/repo", "/existing"],
        )

    def test_streams_subprocess_output_without_selector_pipe_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace = root / "TASK-999.logs"
            raw = root / "TASK-999.raw.logs"
            output = io.StringIO()
            command = [sys.executable, "-c", f"print({REPORT!r}, end='')"]

            with (
                patch("mycodeagent.runner.task_raw_trace_path", return_value=raw),
                contextlib.redirect_stdout(output),
            ):
                result = stream_process_output(
                    command, environment=os.environ.copy(), timeout=10, trace_path=trace
                )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Final review: APPROVED", result.report or "")
            self.assertEqual(raw.read_text(encoding="utf-8"), REPORT)

    def test_returns_structured_failure_when_agent_omits_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace = root / "TASK-133.logs"
            raw = root / "TASK-133.raw.logs"
            output = io.StringIO()
            command = [sys.executable, "-c", "print('implementation is still running')"]

            with (
                patch("mycodeagent.runner.task_raw_trace_path", return_value=raw),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
            ):
                result = stream_process_output(
                    command, environment=os.environ.copy(), timeout=10, trace_path=trace
                )

            self.assertEqual(result.exit_code, 1)
            self.assertIn("- Status: failed", result.report or "")
            self.assertIn("structured final report", result.report or "")
            self.assertIn("WORKFLOW_PROTOCOL_ERROR", trace.read_text(encoding="utf-8"))

    def test_wraps_command_with_caffeinate_on_macos(self) -> None:
        command = ["omnigent", "run", "workflow.yaml"]

        with (
            patch("mycodeagent.runner.sys.platform", "darwin"),
            patch("mycodeagent.runner.shutil.which", return_value="/usr/bin/caffeinate"),
        ):
            wrapped = sleep_preventing_command(command)

        self.assertEqual(wrapped, ["/usr/bin/caffeinate", "-i", *command])

    def test_does_not_wrap_command_on_other_platforms(self) -> None:
        command = ["omnigent", "run", "workflow.yaml"]

        with patch("mycodeagent.runner.sys.platform", "linux"):
            wrapped = sleep_preventing_command(command)

        self.assertIs(wrapped, command)

    def test_detects_wall_clock_suspension_gap(self) -> None:
        started = datetime(2026, 8, 11, tzinfo=timezone.utc)
        ended = started + timedelta(seconds=811)

        self.assertAlmostEqual(suspension_gap_seconds(started, ended, 138), 673.0)


if __name__ == "__main__":
    unittest.main()
