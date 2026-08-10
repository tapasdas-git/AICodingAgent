import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycodeagent.platform_utils import (
    find_project_python,
    repository_relative_posix,
    resolve_executable,
)
from scripts.workflow_helpers import normalized_repository


class PlatformUtilityTests(unittest.TestCase):
    def test_finds_windows_virtual_environment_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            python = root / "venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()

            self.assertEqual(find_project_python(root), python)

    def test_git_path_is_always_posix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            child = root / "workspace" / "sample"
            child.mkdir(parents=True)

            self.assertEqual(repository_relative_posix(child, root), "workspace/sample")

    def test_resolves_executable_from_path(self) -> None:
        self.assertTrue(Path(resolve_executable(Path(sys.executable).name)).is_file())

    def test_normalizes_https_and_ssh_github_remotes(self) -> None:
        https = normalized_repository("https://github.com/Example/Project.git")
        ssh = normalized_repository("git@github.com:Example/Project.git")

        self.assertEqual(https, ssh)

    def test_missing_executable_has_clear_error(self) -> None:
        with patch.dict(os.environ, {"PATH": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "not available on PATH"):
                resolve_executable("definitely-not-installed-mycodeagent-tool")
