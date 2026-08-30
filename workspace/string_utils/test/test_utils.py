"""Tests for the isolated string utility workspace."""

from importlib import import_module

import pytest
from pydantic import ValidationError

from workspace.string_utils.Coding.schemas import StringMetrics
from workspace.string_utils.Coding.utils import (
    StringProcessor,
    calculate_metrics,
    count_words,
    format_title,
    reverse_string,
)


def test_utils_imports_through_repository_package_path() -> None:
    module = import_module("workspace.string_utils.Coding.utils")

    assert module.StringProcessor.reverse_string("package") == "egakcap"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", "olleh"),
        ("A man!", "!nam A"),
        ("", ""),
    ],
)
def test_reverse_string(text: str, expected: str) -> None:
    assert reverse_string(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("one two three", 3),
        ("  one\n\ttwo  ", 2),
        ("", 0),
        ("   ", 0),
    ],
)
def test_count_words(text: str, expected: int) -> None:
    assert count_words(text) == expected


def test_format_title_and_processor_facade() -> None:
    assert format_title("the STRING utility") == "The String Utility"
    assert StringProcessor.format_title("mixed CASE") == "Mixed Case"
    assert StringProcessor.reverse_string("abc") == "cba"
    assert StringProcessor.count_words("one  two") == 2
    assert StringProcessor.title("brief ALIAS") == "Brief Alias"


def test_calculate_metrics_returns_validated_schema() -> None:
    metrics = calculate_metrics("Hello, OpenAI!")

    assert metrics == StringMetrics(
        character_count=14,
        word_count=2,
        vowels_count=6,
    )
    assert StringProcessor.calculate_metrics("Hello, OpenAI!") == metrics
    assert StringProcessor.metrics("Hello, OpenAI!") == metrics


def test_empty_and_whitespace_metrics() -> None:
    assert calculate_metrics("") == StringMetrics(
        character_count=0,
        word_count=0,
        vowels_count=0,
    )
    assert calculate_metrics(" \t") == StringMetrics(
        character_count=2,
        word_count=0,
        vowels_count=0,
    )


@pytest.mark.parametrize(
    "operation",
    [reverse_string, count_words, format_title, calculate_metrics],
)
@pytest.mark.parametrize("invalid", [None, 7, ["text"]])
def test_operations_reject_non_string_inputs(operation: object, invalid: object) -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        operation(invalid)  # type: ignore[operator]


def test_string_metrics_rejects_negative_counts_and_is_immutable() -> None:
    with pytest.raises(ValidationError):
        StringMetrics(character_count=-1, word_count=0, vowels_count=0)

    metrics = StringMetrics(character_count=1, word_count=1, vowels_count=1)
    with pytest.raises(ValidationError):
        metrics.word_count = 2
