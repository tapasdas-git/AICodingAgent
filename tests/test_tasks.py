import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mycodeagent import tasks


class FlexibleTaskSpecTests(unittest.TestCase):
    def _todo(self, root: Path, content: str) -> Path:
        path = root / "TODO.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_infers_workspace_from_minimal_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(
                root,
                "## TASK-107 | working | P3 | [SMOKE] Build Slug Utility in `workspace/slug_utility/`\n"
                "- Outcome: Implement a deterministic slug utility.\n",
            )
            with patch.object(tasks, "ROOT", root):
                spec = tasks.get_task_spec(todo, "TASK-107")
                section = tasks.get_task_section(todo, "TASK-107")

            self.assertEqual(spec.workspace, root / "workspace" / "slug_utility")
            self.assertIn("- Source: `workspace/slug_utility/Coding/`", section)
            self.assertIn("- Tests: `workspace/slug_utility/test/`", section)
            self.assertIn("- Requirements: `workspace/slug_utility/Coding/requirements.txt`", section)

    def test_uses_task_id_workspace_when_title_has_no_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(root, "## TASK-108 | draft | P2 | Build a useful utility\n")
            with patch.object(tasks, "ROOT", root):
                spec = tasks.get_task_spec(todo, "TASK-108")

            self.assertEqual(spec.workspace, root / "workspace" / "task_108")

    def test_accepts_windows_separators_in_title_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(
                root,
                "## TASK-108 | draft | P2 | Build utility in `workspace\\windows_task\\`\n",
            )
            with patch.object(tasks, "ROOT", root):
                spec = tasks.get_task_spec(todo, "TASK-108")

            self.assertEqual(spec.workspace, root / "workspace" / "windows_task")

    def test_rejects_an_inconsistent_optional_test_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(
                root,
                "## TASK-109 | draft | P1 | Build utility in `workspace/right/`\n"
                "- Tests: `workspace/wrong/test/`\n",
            )
            with patch.object(tasks, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "inconsistent Tests path"):
                    tasks.get_task_spec(todo, "TASK-109")

    def test_state_update_is_guarded_and_locked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(root, "## TASK-110 | ready | P1 | Build utility\n")

            self.assertTrue(
                tasks.update_task_state(todo, "TASK-110", "working", expected_state="ready")
            )
            self.assertFalse(
                tasks.update_task_state(todo, "TASK-110", "failed", expected_state="ready")
            )
            self.assertIn("## TASK-110 | working |", todo.read_text(encoding="utf-8"))
            self.assertTrue((root / ".mycodeagent-task-state.lock").is_file())

    def test_ready_task_requires_the_strict_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            todo = self._todo(
                root,
                "## TASK-111 | ready | P1 | Incomplete task in `workspace/incomplete/`\n"
                "### Outcome\nBuild something.\n",
            )
            with patch.object(tasks, "ROOT", root):
                with self.assertRaisesRegex(tasks.TaskReadinessError, "missing or empty sections"):
                    tasks.get_task_spec(todo, "TASK-111")

    def test_complete_strict_task_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            body = """## TASK-112 | ready | P1 | Build slug utility in `workspace/slug/`
### Outcome
Create deterministic slugs.
### Context
The application needs stable URL identifiers.
### Workspace
- Source: `workspace/slug/Coding/`
- Tests: `workspace/slug/test/`
- Requirements: `workspace/slug/Coding/requirements.txt`
### Technology Stack
- Runtime: Python 3.11
### Public API
`slugify(value: str) -> str`
### Functional Requirements
- Normalize words and join them with hyphens.
### Input Validation
- Reject non-string values.
### Error Behavior
- Raise TypeError for non-string values without changing state.
### Performance and Operational Requirements
- Process input in linear time and bounded auxiliary memory.
### Security Requirements
- No external input is executed and no secrets are required.
### Edge Cases
- Empty strings, Unicode text, and repeated separators.
### Acceptance Criteria
- Public import and all listed behaviors are covered by tests.
### Out of Scope
- Transliteration and persistent storage.
"""
            todo = self._todo(root, body)
            with patch.object(tasks, "ROOT", root):
                spec = tasks.get_task_spec(todo, "TASK-112")

            self.assertEqual(spec.workspace, root / "workspace" / "slug")


if __name__ == "__main__":
    unittest.main()
