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


if __name__ == "__main__":
    unittest.main()
