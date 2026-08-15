"""Tests for the public string utility API."""

from __future__ import annotations

import pytest

from Coding import (
    normalize_text,
    to_camel_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
    to_title_case,
)


def test_public_package_exports_all_helpers() -> None:
    import Coding

    assert set(Coding.__all__) == {
        "normalize_text",
        "to_camel_case",
        "to_kebab_case",
        "to_pascal_case",
        "to_snake_case",
        "to_title_case",
    }


def test_normalize_text_trims_and_collapses_unicode_whitespace() -> None:
    assert normalize_text("  Hello\tworld\nfrom\u2003Python  ") == "Hello world from Python"


@pytest.mark.parametrize(
    ("converter", "expected"),
    [
        (to_snake_case, "http_response_code_200"),
        (to_kebab_case, "http-response-code-200"),
        (to_camel_case, "httpResponseCode200"),
        (to_pascal_case, "HttpResponseCode200"),
        (to_title_case, "Http Response Code 200"),
    ],
)
def test_case_conversion_handles_acronyms_and_digits(converter, expected: str) -> None:
    assert converter("HTTPResponse code-200") == expected


@pytest.mark.parametrize(
    "value",
    ["already_snake_case", "mixed---separators__and spaces", "  MixedCase  "],
)
def test_snake_case_has_stable_separators(value: str) -> None:
    assert to_snake_case(value).strip("_") == to_snake_case(value)
    assert "__" not in to_snake_case(value)


@pytest.mark.parametrize(
    "converter",
    [normalize_text, to_snake_case, to_kebab_case, to_camel_case, to_pascal_case, to_title_case],
)
def test_empty_input_returns_empty_string(converter) -> None:
    assert converter(" \t\n ") == ""


@pytest.mark.parametrize(
    "converter",
    [normalize_text, to_snake_case, to_kebab_case, to_camel_case, to_pascal_case, to_title_case],
)
def test_non_string_input_is_rejected(converter) -> None:
    with pytest.raises(TypeError, match=r"value must be a string, got int"):
        converter(123)


def test_case_conversion_preserves_unicode_letters() -> None:
    assert to_snake_case("Crème Brûlée") == "crème_brûlée"
