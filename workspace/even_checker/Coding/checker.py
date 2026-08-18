"""Utilities for determining integer parity."""


def is_even(value: int) -> bool:
    """Return whether ``value`` is an even integer.

    Booleans are rejected explicitly because, despite inheriting from
    :class:`int`, they are logical values rather than integer inputs for this
    utility.

    Args:
        value: The integer whose parity should be checked.

    Raises:
        TypeError: If ``value`` is a boolean or is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer")

    return value % 2 == 0
