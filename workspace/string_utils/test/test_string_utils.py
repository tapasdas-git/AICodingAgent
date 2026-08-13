"""Acceptance and regression tests for the string utility helpers."""

from pathlib import Path
import sys

import pytest

CODING_DIR = Path(__file__).resolve().parents[1] / "Coding"
sys.path.insert(0, str(CODING_DIR))

from string_utils import (  # noqa: E402
    normalize_text,
    to_camel_case,
    to_kebab_case,
    to_lower_case,
    to_snake_case,
    to_title_case,
    to_upper_case,
)


def test_normalize_text_trims_and_collapses_all_whitespace() -> None:
    assert normalize_text("  Hello\t\n  World  ") == "Hello World"
    assert normalize_text("") == ""
    assert normalize_text(" \t\n ") == ""


def test_basic_case_conversion_normalizes_first() -> None:
    value = "  hELLo   wORLD  "
    assert to_lower_case(value) == "hello world"
    assert to_upper_case(value) == "HELLO WORLD"
    assert to_title_case(value) == "Hello World"


def test_separator_case_conversion_handles_mixed_separators() -> None:
    value = "  Hello_world--AGAIN  "
    assert to_snake_case(value) == "hello_world_again"
    assert to_kebab_case(value) == "hello-world-again"
    assert to_camel_case(value) == "helloWorldAgain"


def test_separator_case_conversion_splits_camel_case() -> None:
    assert to_snake_case("requestLatency Metric") == "request_latency_metric"
    assert to_kebab_case("requestLatency Metric") == "request-latency-metric"


@pytest.mark.parametrize(
    "helper",
    [
        normalize_text,
        to_lower_case,
        to_upper_case,
        to_title_case,
        to_snake_case,
        to_kebab_case,
        to_camel_case,
    ],
)
def test_helpers_reject_non_string_values(helper) -> None:
    with pytest.raises(TypeError, match="value must be a string"):
        helper(None)


@pytest.mark.parametrize("helper", [to_snake_case, to_kebab_case, to_camel_case])
def test_separator_helpers_return_empty_for_no_words(helper) -> None:
    assert helper(" --- !!! ") == ""


def test_unicode_letters_are_preserved() -> None:
    assert to_kebab_case("  CAFÉ déjà  ") == "café-déjà"
