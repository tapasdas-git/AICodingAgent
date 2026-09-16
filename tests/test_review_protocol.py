"""Tests for evidence-backed reviewer report validation."""

from pathlib import Path

from mycodeagent.protocol import validate_review_report


SUMMARY = """## Review summary
- Scope: `workspace/sample/`
- Tech stack: Python 3.11, standard library
- Tests: `pytest -v` — passed
- Code quality: public API and errors inspected
- Performance: linear workload; not performance-sensitive
- Test quality: requirements and failure paths covered
- Security: no external trust boundary
"""


def test_accepts_complete_approved_review(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace" / "sample"
    workspace.mkdir(parents=True)
    report = "APPROVED\n" + SUMMARY + "## Findings\n- None"

    assert validate_review_report(report, workspace, tmp_path) == []


def test_rejects_invented_file_and_unknown_guideline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace" / "sample"
    workspace.mkdir(parents=True)
    report = (
        "CHANGES_REQUESTED\n" + SUMMARY + "## Findings\n"
        "- [F1] High [MADEUP-01] — `Coding/missing.py:99` — "
        "Defect: validation is absent. Impact: invalid data is accepted. "
        "Evidence: direct path inspection. Required fix: validate the input."
    )

    errors = validate_review_report(report, workspace, tmp_path)

    assert any("unknown guideline" in error for error in errors)
    assert any("does not exist" in error for error in errors)


def test_accepts_evidenced_finding_with_real_line(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace" / "sample"
    source = workspace / "Coding" / "engine.py"
    source.parent.mkdir(parents=True)
    source.write_text("def calculate():\n    return None\n", encoding="utf-8")
    report = (
        "CHANGES_REQUESTED\n" + SUMMARY + "## Findings\n"
        "- [F1] Medium [COR-02] — `Coding/engine.py:1` — "
        "Defect: the public input has no validation. Impact: invalid values reach execution. "
        "Evidence: calculate accepts no validated request boundary. Required fix: add a validated parameter."
    )

    assert validate_review_report(report, workspace, tmp_path) == []
