"""Deterministic documentation and test-quality checks for task workspaces."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Any


PLACEHOLDER_COMMENT = re.compile(r"\b(?:TODO|FIXME|XXX|PLACEHOLDER)\b", re.IGNORECASE)


def _issue(rule: str, path: Path, line: int, message: str) -> dict[str, Any]:
    return {"rule": rule, "path": path.as_posix(), "line": line, "message": message}


def _public_definition_issues(tree: ast.AST, path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        if ast.get_docstring(node, clean=False) is None:
            kind = "class" if isinstance(node, ast.ClassDef) else "function or method"
            issues.append(
                _issue("DOC-02", path, node.lineno, f"public {kind} {node.name!r} has no docstring")
            )
    return issues


def _placeholder_issues(source: str, path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT and PLACEHOLDER_COMMENT.search(token.string):
                issues.append(
                    _issue("DOC-05", path, token.start[0], "unresolved placeholder comment")
                )
    except (IndentationError, tokenize.TokenError):
        pass
    return issues


def _has_meaningful_assertion(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if not isinstance(child, ast.Call):
            continue
        function = child.func
        if isinstance(function, ast.Attribute):
            if function.attr == "raises" and isinstance(function.value, ast.Name) and function.value.id == "pytest":
                return True
            if function.attr.startswith("assert") or function.attr in {"fail", "assertRaises"}:
                return True
    return False


def _test_assertion_issues(tree: ast.AST, path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            if not _has_meaningful_assertion(node):
                issues.append(
                    _issue("TEST-01", path, node.lineno, f"test {node.name!r} has no meaningful assertion")
                )
    return issues


def run_quality_checks(
    workspace: Path,
    *,
    require_public_docstrings: bool = True,
    reject_placeholder_comments: bool = True,
    require_test_assertions: bool = True,
) -> dict[str, Any]:
    """Inspect Python source and tests and return a JSON-serializable result."""
    coding_dir, test_dir = workspace / "Coding", workspace / "test"
    issues: list[dict[str, Any]] = []
    checked_files = 0
    area_counts = {"source": 0, "test": 0}
    for area, directory in (("source", coding_dir), ("test", test_dir)):
        if not directory.is_dir():
            issues.append(
                _issue("SCOPE-01", directory.relative_to(workspace), 1, f"required {area} directory is missing")
            )
            continue
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            area_counts[area] += 1
            checked_files += 1
            relative = path.relative_to(workspace)
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(relative))
            except SyntaxError as error:
                issues.append(
                    _issue("COR-01", relative, error.lineno or 1, f"Python syntax error: {error.msg}")
                )
                continue
            if area == "source":
                if require_public_docstrings and ast.get_docstring(tree, clean=False) is None:
                    issues.append(_issue("DOC-01", relative, 1, "public module has no docstring"))
                if require_public_docstrings:
                    issues.extend(_public_definition_issues(tree, relative))
                if reject_placeholder_comments:
                    issues.extend(_placeholder_issues(source, relative))
            elif require_test_assertions:
                issues.extend(_test_assertion_issues(tree, relative))
    for area, directory in (("source", coding_dir), ("test", test_dir)):
        if directory.is_dir() and area_counts[area] == 0:
            issues.append(
                _issue("SCOPE-01", directory.relative_to(workspace), 1, f"required {area} directory has no Python files")
            )
    return {
        "status": "passed" if not issues else "failed",
        "checked_files": checked_files,
        "issues": issues,
    }
