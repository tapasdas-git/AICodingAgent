"""Regression checks for the supervisor/worker result-handoff contract."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "coding_agent.yaml"
RUNTIME = ROOT / "workflow_runtime.toml"


def test_supervisor_can_retrieve_active_worker_terminal_report() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "use `sys_read_inbox` only to wait for and" in workflow
    assert "retrieve the result of that same active worker" in workflow
    assert "including `sys_session_get_info`, `sys_read_inbox`, or" not in workflow


def test_empty_inbox_result_does_not_fail_or_replace_worker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "repeated empty\n    `sys_read_inbox` results are not a terminal failure" in workflow
    assert "without launching a replacement or advancing the workflow" in workflow


def test_token_budget_and_report_audit_are_configured() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    with RUNTIME.open("rb") as runtime_file:
        runtime = tomllib.load(runtime_file)
    for key in ("token_budget", "supervisor_token_budget", "implementer_token_budget", "reviewer_token_budget"):
        assert runtime[key] > 0
    assert "callable: mycodeagent.workflow_tools.record_token_usage" in workflow
    assert "callable: mycodeagent.workflow_tools.record_agent_report" in workflow
