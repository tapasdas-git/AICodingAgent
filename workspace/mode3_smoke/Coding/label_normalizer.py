"""Utilities for converting human-readable labels to canonical identifiers."""


def normalize_label(value: str) -> str:
    """Return a case-folded, hyphen-separated label.

    Args:
        value: The label to normalize.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If ``value`` contains no non-whitespace characters.
    """
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    words = value.casefold().split()
    if not words:
        raise ValueError("value must not be empty or whitespace-only")

    return "-".join(words)
