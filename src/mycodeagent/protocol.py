"""Parsing and validation for terminal workflow reports."""

from __future__ import annotations

import re
from pathlib import Path


REPORT_PATTERNS = (
    (r"# Task workflow:[^\n]*", ("## Outcome", "## Execution summary", "## Next action", "- Final review:")),
    (r"# Implementation:[^\n]*", ("## Status", "## Changed files", "## Validation")),
    (r"## Pull request\s*", ("- Status:",)),
    (r"## Changelog\s*", ("- Status:",)),
    (r"(?:^|[^A-Z_])(APPROVED|CHANGES_REQUESTED)\s*$", ()),
)

GUIDELINE_IDS = {
    *(f"DOC-{number:02d}" for number in range(1, 6)),
    *(f"COR-{number:02d}" for number in range(1, 6)),
    *(f"PERF-{number:02d}" for number in range(1, 5)),
    *(f"SEC-{number:02d}" for number in range(1, 5)),
    *(f"TEST-{number:02d}" for number in range(1, 6)),
    *(f"SCOPE-{number:02d}" for number in range(1, 4)),
    *(f"REVIEW-{number:02d}" for number in range(1, 6)),
}
REVIEW_SUMMARY_FIELDS = (
    "- Tech stack:",
    "- Tests:",
    "- Code quality:",
    "- Performance:",
    "- Test quality:",
    "- Security:",
)
FINDING_PATTERN = re.compile(
    r"^- \[(F\d+)\] (Critical|High|Medium|Low) \[([A-Z]+-\d{2})\] — "
    r"`([^`]+):(\d+)` — Defect: (.+?) Impact: (.+?) Evidence: (.+?) "
    r"Required fix: (.+)$",
    re.MULTILINE,
)


def extract_structured_report(raw_output: list[str]) -> str | None:
    """Return the last complete terminal report from streamed output."""
    output = "".join(raw_output).strip()
    if not output:
        return None
    for pattern, required_sections in REPORT_PATTERNS:
        matches = list(re.finditer(pattern, output, flags=re.MULTILINE))
        if not matches:
            continue
        match = matches[-1]
        report_start = match.start(1) if match.lastindex else match.start()
        report = output[report_start:]
        if all(section in report for section in required_sections):
            return report
    return None


def validate_review_report(report: str, workspace: Path, root: Path) -> list[str]:
    """Return evidence-validation errors for a terminal reviewer report."""
    stripped = report.strip()
    first_line = stripped.splitlines()[0] if stripped else ""
    if first_line not in {"APPROVED", "CHANGES_REQUESTED"}:
        return ["review must begin exactly with APPROVED or CHANGES_REQUESTED"]
    errors = [f"review is missing required field {field}" for field in REVIEW_SUMMARY_FIELDS if field not in stripped]
    if "## Findings" not in stripped:
        errors.append("review is missing ## Findings")
    if first_line == "APPROVED":
        if not re.search(r"^## Findings\s*\n- None\s*(?=\n## |\Z)", stripped, re.MULTILINE):
            errors.append("approved review must contain an empty Findings section")
        return errors

    matches = list(FINDING_PATTERN.finditer(stripped))
    finding_lines = [line for line in stripped.splitlines() if line.startswith("- [F")]
    if not matches:
        errors.append("changes-requested review must contain at least one structured finding")
        return errors
    if len(matches) != len(finding_lines):
        errors.append("every finding must use the required evidence format")
    identifiers: set[str] = set()
    workspace = workspace.resolve()
    root = root.resolve()
    for match in matches:
        finding_id, _, guideline_id, path_text, line_text, *_ = match.groups()
        if finding_id in identifiers:
            errors.append(f"duplicate finding identifier {finding_id}")
        identifiers.add(finding_id)
        if guideline_id not in GUIDELINE_IDS:
            errors.append(f"finding {finding_id} uses unknown guideline {guideline_id}")
        reported_path = Path(path_text)
        if reported_path.is_absolute():
            candidate = reported_path.resolve()
        elif reported_path.parts and reported_path.parts[0] == "workspace":
            candidate = (root / reported_path).resolve()
        else:
            candidate = (workspace / reported_path).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError:
            errors.append(f"finding {finding_id} path is outside the task workspace")
            continue
        if not candidate.is_file():
            errors.append(f"finding {finding_id} cites a file that does not exist")
            continue
        line_number = int(line_text)
        line_count = len(candidate.read_text(encoding="utf-8").splitlines())
        if line_number < 1 or line_number > line_count:
            errors.append(f"finding {finding_id} cites invalid line {line_number}")
    return errors
