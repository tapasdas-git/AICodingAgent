"""Regression checks for the supervisor/worker result-handoff contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "coding_agent.yaml"


def test_supervisor_can_retrieve_active_worker_terminal_report() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "use `sys_read_inbox` only to wait for and" in workflow
    assert "retrieve the result of that same active worker" in workflow
    assert "including `sys_session_get_info`, `sys_read_inbox`, or" not in workflow


def test_empty_inbox_result_does_not_fail_or_replace_worker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "repeated empty\n    `sys_read_inbox` results are not a terminal failure" in workflow
    assert "without launching a replacement or advancing the workflow" in workflow
