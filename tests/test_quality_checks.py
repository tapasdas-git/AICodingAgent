"""Tests for deterministic task documentation and test-quality checks."""

from pathlib import Path

from mycodeagent.quality_checks import run_quality_checks


def _workspace(tmp_path: Path, source: str, tests: str) -> Path:
    workspace = tmp_path / "workspace" / "sample"
    (workspace / "Coding").mkdir(parents=True)
    (workspace / "test").mkdir()
    (workspace / "Coding" / "sample.py").write_text(source, encoding="utf-8")
    (workspace / "test" / "test_sample.py").write_text(tests, encoding="utf-8")
    return workspace


def test_accepts_documented_public_api_and_meaningful_tests(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        '"""Documented module."""\n\ndef add(left: int, right: int) -> int:\n'
        '    """Return the sum."""\n    return left + right\n',
        "def test_add():\n    assert 1 + 1 == 2\n",
    )

    result = run_quality_checks(workspace)

    assert result["status"] == "passed"
    assert result["issues"] == []


def test_reports_missing_docstrings_placeholders_and_assertions(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        "# TODO replace this\n\ndef add(left: int, right: int) -> int:\n    return left + right\n",
        "def test_add():\n    value = 1 + 1\n",
    )

    result = run_quality_checks(workspace)
    rules = {issue["rule"] for issue in result["issues"]}

    assert result["status"] == "failed"
    assert {"DOC-01", "DOC-02", "DOC-05", "TEST-01"} <= rules


def test_accepts_pytest_raises_as_a_meaningful_assertion(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        '"""Module."""\n',
        "import pytest\n\ndef test_failure():\n    with pytest.raises(ValueError):\n        raise ValueError\n",
    )

    assert run_quality_checks(workspace)["status"] == "passed"
