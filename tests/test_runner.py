import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycodeagent.runner import stream_process_output


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


if __name__ == "__main__":
    unittest.main()
