"""Lightweight, dependency-free helpers for normalizing and converting text."""

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

_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD_SEPARATOR = re.compile(r"[\W_]+", flags=re.UNICODE)


def _require_string(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("value must be a string")


def normalize_text(value: str) -> str:
    """Trim *value* and collapse every run of whitespace to one space."""

    _require_string(value)
    return " ".join(value.split())


def _words(value: str) -> list[str]:
    """Return normalized words, including boundaries in ``camelCase`` text."""

    normalized = normalize_text(value)
    separated = _WORD_BOUNDARY.sub(" ", normalized)
    return [word for word in _WORD_SEPARATOR.sub(" ", separated).split() if word]


def to_lower_case(value: str) -> str:
    """Return normalized text using Unicode-aware lowercase conversion."""

    return normalize_text(value).lower()


def to_upper_case(value: str) -> str:
    """Return normalized text using Unicode-aware uppercase conversion."""

    return normalize_text(value).upper()


def to_title_case(value: str) -> str:
    """Return normalized text in title case."""

    return normalize_text(value).title()


def to_snake_case(value: str) -> str:
    """Join words from *value* with underscores in lowercase."""

    return "_".join(word.lower() for word in _words(value))


def to_kebab_case(value: str) -> str:
    """Join words from *value* with hyphens in lowercase."""

    return "-".join(word.lower() for word in _words(value))


def to_camel_case(value: str) -> str:
    """Join words from *value* in lower camel case."""

    words = _words(value)
    if not words:
        return ""
    first, *rest = words
    return first.lower() + "".join(word[:1].upper() + word[1:].lower() for word in rest)
