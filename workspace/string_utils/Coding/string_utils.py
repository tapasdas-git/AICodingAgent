"""Small, dependency-free helpers for normalizing and converting text."""

from __future__ import annotations

import re

_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CASE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_SEPARATOR = re.compile(r"[^\w]+", flags=re.UNICODE)
_UNDERSCORES = re.compile(r"_+")


def _require_string(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"value must be a string, got {type(value).__name__}")
    return value


def normalize_text(value: str) -> str:
    """Trim text and replace each run of whitespace with one space."""

    return " ".join(_require_string(value).split())


def _words(value: str) -> list[str]:
    text = _require_string(value).strip()
    text = _ACRONYM_BOUNDARY.sub(r"\1 \2", text)
    text = _CASE_BOUNDARY.sub(r"\1 \2", text)
    text = _SEPARATOR.sub(" ", text.replace("_", " "))
    return text.lower().split()


def to_snake_case(value: str) -> str:
    """Convert text to lower-case words separated by underscores."""

    return _UNDERSCORES.sub("_", "_".join(_words(value)))


def to_kebab_case(value: str) -> str:
    """Convert text to lower-case words separated by hyphens."""

    return "-".join(_words(value))


def to_camel_case(value: str) -> str:
    """Convert text to lower camelCase."""

    words = _words(value)
    if not words:
        return ""
    return words[0] + "".join(word.capitalize() for word in words[1:])


def to_pascal_case(value: str) -> str:
    """Convert text to PascalCase."""

    return "".join(word.capitalize() for word in _words(value))


def to_title_case(value: str) -> str:
    """Convert text to space-separated Title Case."""

    return " ".join(word.capitalize() for word in _words(value))
