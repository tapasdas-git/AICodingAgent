"""Acceptance tests for the string utility helpers."""

from pathlib import Path
import sys
from typing import Callable

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


def test_normalize_text_handles_whitespace_and_empty_values() -> None:
    assert normalize_text("  Hello\t\n  World  ") == "Hello World"
    assert normalize_text("") == ""
    assert normalize_text(" \t\n ") == ""


def test_basic_case_conversions_normalize_text() -> None:
    value = "  hELLo   wORLD  "
    assert to_lower_case(value) == "hello world"
    assert to_upper_case(value) == "HELLO WORLD"
    assert to_title_case(value) == "Hello World"


def test_word_case_conversions_support_common_separators() -> None:
    value = "  Hello_world--AGAIN  "
    assert to_snake_case(value) == "hello_world_again"
    assert to_kebab_case(value) == "hello-world-again"
    assert to_camel_case(value) == "helloWorldAgain"


def test_word_case_conversions_split_camel_case() -> None:
    value = "requestLatency Metric"
    assert to_snake_case(value) == "request_latency_metric"
    assert to_kebab_case(value) == "request-latency-metric"
    assert to_camel_case(value) == "requestLatencyMetric"


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
def test_all_public_helpers_reject_non_strings(helper: Callable[[str], str]) -> None:
    with pytest.raises(TypeError, match="value must be a string"):
        helper(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("helper", [to_snake_case, to_kebab_case, to_camel_case])
def test_word_case_conversions_handle_input_without_words(
    helper: Callable[[str], str],
) -> None:
    assert helper(" --- !!! ") == ""


def test_unicode_text_is_preserved() -> None:
    assert to_kebab_case("  CAFÉ déjà  ") == "café-déjà"
