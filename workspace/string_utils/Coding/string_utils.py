"""Dependency-free helpers for normalizing text and converting its case."""

from __future__ import annotations

import re

__all__ = [
    "normalize_text",
    "to_camel_case",
    "to_kebab_case",
    "to_lower_case",
    "to_snake_case",
    "to_title_case",
    "to_upper_case",
]

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[\W_]+", flags=re.UNICODE)


def _require_string(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("value must be a string")


def normalize_text(value: str) -> str:
    """Strip surrounding whitespace and collapse internal whitespace."""

    _require_string(value)
    return " ".join(value.split())


def _words(value: str) -> list[str]:
    normalized = normalize_text(value)
    with_boundaries = _CAMEL_BOUNDARY.sub(" ", normalized)
    return _SEPARATORS.sub(" ", with_boundaries).split()


def to_lower_case(value: str) -> str:
    """Return normalized text converted to lowercase."""

    return normalize_text(value).lower()


def to_upper_case(value: str) -> str:
    """Return normalized text converted to uppercase."""

    return normalize_text(value).upper()


def to_title_case(value: str) -> str:
    """Return normalized text converted to title case."""

    return normalize_text(value).title()


def to_snake_case(value: str) -> str:
    """Return words joined in lowercase snake case."""

    return "_".join(word.lower() for word in _words(value))


def to_kebab_case(value: str) -> str:
    """Return words joined in lowercase kebab case."""

    return "-".join(word.lower() for word in _words(value))


def to_camel_case(value: str) -> str:
    """Return words joined in lower camel case."""

    words = _words(value)
    if not words:
        return ""
    first, *rest = words
    return first.lower() + "".join(word.capitalize() for word in rest)
