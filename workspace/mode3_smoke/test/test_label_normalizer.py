"""Tests for the label-normalization utility."""

import pytest

from workspace.mode3_smoke.Coding.label_normalizer import normalize_label


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Hello   World  ", "hello-world"),
        ("MiXeD Case", "mixed-case"),
        ("words\tseparated\nby whitespace", "words-separated-by-whitespace"),
    ],
)
def test_normalize_label(value: str, expected: str) -> None:
    assert normalize_label(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_label_rejects_empty_values(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_label(value)


@pytest.mark.parametrize("value", [None, 123, ["label"]])
def test_normalize_label_rejects_non_strings(value: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        normalize_label(value)  # type: ignore[arg-type]
