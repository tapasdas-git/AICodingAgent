"""Extensible arithmetic operation strategies and their registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, DecimalException
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

from exceptions import (
    ArithmeticDomainError,
    ConfigurationError,
    DivisionByZeroError,
    SizeLimitError,
)


class Associativity(str, Enum):
    """Supported binary-operator associativity modes."""

    LEFT = "left"
    RIGHT = "right"


class OperationStrategy(ABC):
    """Contract implemented by every registered binary operator."""

    symbol: str
    precedence: int
    associativity: Associativity

    @abstractmethod
    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Apply the operation to two validated Decimal operands."""


class AdditionStrategy(OperationStrategy):
    """Add two operands."""

    symbol = "+"
    precedence = 1
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the sum of both operands."""
        return left + right


class SubtractionStrategy(OperationStrategy):
    """Subtract the right operand from the left operand."""

    symbol = "-"
    precedence = 1
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the difference between both operands."""
        return left - right


class MultiplicationStrategy(OperationStrategy):
    """Multiply two operands."""

    symbol = "*"
    precedence = 2
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the product of both operands."""
        return left * right


class DivisionStrategy(OperationStrategy):
    """Divide the left operand by a non-zero right operand."""

    symbol = "/"
    precedence = 2
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the quotient or raise a domain-specific zero error."""
        if right == 0:
            raise DivisionByZeroError("Cannot divide by zero")
        return left / right


class ExponentiationStrategy(OperationStrategy):
    """Raise the left operand to the right operand with a resource bound."""

    symbol = "^"
    precedence = 3
    associativity = Associativity.RIGHT

    def __init__(self, max_abs_exponent: int = 10_000) -> None:
        if max_abs_exponent < 1:
            raise ConfigurationError("max_abs_exponent must be at least 1")
        self._max_abs_exponent = max_abs_exponent

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left`` raised to ``right`` within the configured bound."""
        if abs(right) > self._max_abs_exponent:
            raise SizeLimitError(
                f"Exponent {right} exceeds the configured absolute limit "
                f"of {self._max_abs_exponent}"
            )
        if left.is_zero() and right < 0:
            raise DivisionByZeroError("Cannot raise zero to a negative exponent")
        try:
            result = left**right
        except (DecimalException, ValueError, OverflowError) as exc:
            raise ArithmeticDomainError(
                f"Cannot raise {left} to exponent {right} using Decimal arithmetic"
            ) from exc
        if not result.is_finite():
            raise ArithmeticDomainError(
                f"Exponentiation of {left} by {right} produced a non-finite result"
            )
        return result


class OperationRegistry:
    """Own and validate the operator strategies available to evaluation."""

    def __init__(self, strategies: Iterable[OperationStrategy] = ()) -> None:
        self._strategies: dict[str, OperationStrategy] = {}
        for strategy in strategies:
            self.register(strategy)

    @classmethod
    def with_defaults(cls, max_abs_exponent: int = 10_000) -> OperationRegistry:
        """Create a registry containing the five standard operators."""
        return cls(
            (
                AdditionStrategy(),
                SubtractionStrategy(),
                MultiplicationStrategy(),
                DivisionStrategy(),
                ExponentiationStrategy(max_abs_exponent),
            )
        )

    def register(self, strategy: OperationStrategy, *, replace: bool = False) -> None:
        """Register a validated strategy, optionally replacing its symbol."""
        if not isinstance(strategy, OperationStrategy):
            raise ConfigurationError("strategy must implement OperationStrategy")
        symbol = strategy.symbol
        if (
            not isinstance(symbol, str)
            or not symbol
            or any(char.isspace() or char.isalnum() or char in ".()" for char in symbol)
        ):
            raise ConfigurationError(
                "Operator symbols must be non-empty punctuation excluding '.', '(' and ')'"
            )
        if not isinstance(strategy.precedence, int) or strategy.precedence < 1:
            raise ConfigurationError("Operator precedence must be a positive integer")
        if not isinstance(strategy.associativity, Associativity):
            raise ConfigurationError("Operator associativity must be an Associativity value")
        if symbol in self._strategies and not replace:
            raise ConfigurationError(f"Operator {symbol!r} is already registered")
        self._strategies[symbol] = strategy

    def get(self, symbol: str) -> OperationStrategy:
        """Return the strategy for ``symbol`` or report it as unsupported."""
        try:
            return self._strategies[symbol]
        except KeyError as exc:
            raise ConfigurationError(f"Operator {symbol!r} is not registered") from exc

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return symbols longest-first for deterministic token matching."""
        return tuple(sorted(self._strategies, key=lambda value: (-len(value), value)))

    @property
    def strategies(self) -> Mapping[str, OperationStrategy]:
        """Return a read-only view of registered strategies."""
        return MappingProxyType(self._strategies)
