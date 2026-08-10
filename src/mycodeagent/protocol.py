"""Parsing and validation for terminal workflow reports."""

from __future__ import annotations

import re


REPORT_PATTERNS = (
    (r"# Task workflow:[^\n]*", ("## Outcome", "## Execution summary", "## Next action", "- Final review:")),
    (r"# Implementation:[^\n]*", ("## Status", "## Changed files", "## Validation")),
    (r"## Pull request\s*", ("- Status:",)),
    (r"## Changelog\s*", ("- Status:",)),
    (r"(?:^|[^A-Z_])(APPROVED|CHANGES_REQUESTED)\s*$", ()),
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
