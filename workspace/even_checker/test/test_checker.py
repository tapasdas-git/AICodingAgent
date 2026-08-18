"""Tests for the even-number checker."""

import pytest

from workspace.even_checker.Coding.checker import is_even


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, True),
        (7, False),
        (-8, True),
        (-3, False),
        (0, True),
    ],
)
def test_is_even_for_integers(value: int, expected: bool) -> None:
    assert is_even(value) is expected


@pytest.mark.parametrize("value", [True, False])
def test_is_even_rejects_booleans(value: bool) -> None:
    with pytest.raises(TypeError, match="value must be an integer"):
        is_even(value)


@pytest.mark.parametrize("value", [1.0, "2", None, [2]])
def test_is_even_rejects_non_integers(value: object) -> None:
    with pytest.raises(TypeError, match="value must be an integer"):
        is_even(value)  # type: ignore[arg-type]
