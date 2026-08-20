"""Utilities for identifying prime numbers and finding prime factors."""


def _require_integer(value: int) -> None:
    """Reject values outside the public functions' integer contract."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("n must be an integer")


def is_prime(n: int) -> bool:
    """Return whether *n* is a prime number."""
    _require_integer(n)
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    divisor = 5
    while divisor * divisor <= n:
        if n % divisor == 0 or n % (divisor + 2) == 0:
            return False
        divisor += 6
    return True


def get_prime_factors(n: int) -> list[int]:
    """Return the prime factors of *n* in ascending order.

    Factorization is defined for integers greater than one. Repeated factors
    are retained, so ``get_prime_factors(18)`` returns ``[2, 3, 3]``.
    """
    _require_integer(n)
    if n <= 1:
        raise ValueError("n must be greater than one")

    factors: list[int] = []
    divisor = 2
    while divisor * divisor <= n:
        while n % divisor == 0:
            factors.append(divisor)
            n //= divisor
        divisor = 3 if divisor == 2 else divisor + 2

    if n > 1:
        factors.append(n)
    return factors
