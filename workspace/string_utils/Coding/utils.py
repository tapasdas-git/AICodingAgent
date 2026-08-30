"""Stateless helpers for common string manipulation and statistics."""

from .schemas import StringMetrics

_VOWELS = frozenset("aeiouAEIOU")


def _validate_text(text: str) -> None:
    """Reject values that do not satisfy the public string contract."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")


def reverse_string(text: str) -> str:
    """Return *text* with its Unicode code points in reverse order."""

    _validate_text(text)
    return text[::-1]


def count_words(text: str) -> int:
    """Count groups of non-whitespace characters in *text*."""

    _validate_text(text)
    return len(text.split())


def format_title(text: str) -> str:
    """Return *text* in Python's Unicode-aware title-case format."""

    _validate_text(text)
    return text.title()


def calculate_metrics(text: str) -> StringMetrics:
    """Calculate validated character, word, and vowel counts for *text*."""

    _validate_text(text)
    return StringMetrics(
        character_count=len(text),
        word_count=len(text.split()),
        vowels_count=sum(character in _VOWELS for character in text),
    )


class StringProcessor:
    """Namespaced access to the stateless string operations."""

    reverse_string = staticmethod(reverse_string)
    count_words = staticmethod(count_words)
    format_title = staticmethod(format_title)
    calculate_metrics = staticmethod(calculate_metrics)

    # Concise aliases keep the facade convenient without duplicating behavior.
    reverse = staticmethod(reverse_string)
    word_count = staticmethod(count_words)
    title = staticmethod(format_title)
    metrics = staticmethod(calculate_metrics)
