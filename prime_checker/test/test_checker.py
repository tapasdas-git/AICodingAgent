"""Tests for the prime checker utilities."""

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "Coding" / "checker.py"
SPEC = importlib.util.spec_from_file_location("prime_checker", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.mark.parametrize("value", [-10, 0, 1, 4, 9, 25, 35])
def test_is_prime_rejects_non_primes(value: int) -> None:
    assert checker.is_prime(value) is False


@pytest.mark.parametrize("value", [2, 3, 5, 7, 29])
def test_is_prime_accepts_primes(value: int) -> None:
    assert checker.is_prime(value) is True


@pytest.mark.parametrize("value", [True, 2.5, "7"])
def test_is_prime_requires_an_integer(value: object) -> None:
    with pytest.raises(TypeError, match="n must be an integer"):
        checker.is_prime(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(2, [2]), (18, [2, 3, 3]), (49, [7, 7]), (60, [2, 2, 3, 5])],
)
def test_get_prime_factors(value: int, expected: list[int]) -> None:
    assert checker.get_prime_factors(value) == expected


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_get_prime_factors_requires_value_greater_than_one(value: int) -> None:
    with pytest.raises(ValueError, match="n must be greater than one"):
        checker.get_prime_factors(value)


@pytest.mark.parametrize("value", [False, 3.5, "18"])
def test_get_prime_factors_requires_an_integer(value: object) -> None:
    with pytest.raises(TypeError, match="n must be an integer"):
        checker.get_prime_factors(value)
