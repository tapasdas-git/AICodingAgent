"""Extensible arithmetic operation strategies and their registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, DecimalException
from types import MappingProxyType
from typing import Literal, Mapping

if __package__:
    from .exceptions import (
        ConfigurationError,
        DivisionByZeroError,
        EvaluationError,
        UnsupportedOperatorError,
    )
else:
    from exceptions import (
        ConfigurationError,
        DivisionByZeroError,
        EvaluationError,
        UnsupportedOperatorError,
    )

Associativity = Literal["left", "right"]


class OperatorStrategy(ABC):
    """Contract implemented by every unary or binary arithmetic operator."""

    symbol: str
    precedence: int
    associativity: Associativity
    arity: int = 2

    @abstractmethod
    def apply(self, *operands: Decimal) -> Decimal:
        """Return the result of applying this strategy to validated operands."""


class AdditionStrategy(OperatorStrategy):
    """Add two Decimal operands."""

    symbol, precedence, associativity = "+", 1, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        """Return the sum of two operands."""
        return operands[0] + operands[1]


class SubtractionStrategy(OperatorStrategy):
    """Subtract the right Decimal operand from the left one."""

    symbol, precedence, associativity = "-", 1, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        """Return the difference between two operands."""
        return operands[0] - operands[1]


class MultiplicationStrategy(OperatorStrategy):
    """Multiply two Decimal operands."""

    symbol, precedence, associativity = "*", 2, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        """Return the product of two operands."""
        return operands[0] * operands[1]


class DivisionStrategy(OperatorStrategy):
    """Divide the left Decimal operand by the right one."""

    symbol, precedence, associativity = "/", 2, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        """Return the quotient, rejecting a zero divisor explicitly."""
        if operands[1] == 0:
            raise DivisionByZeroError("Cannot divide by zero.")
        return operands[0] / operands[1]


class ExponentiationStrategy(OperatorStrategy):
    """Raise the left Decimal operand to the right Decimal power."""

    symbol, precedence, associativity = "^", 3, "right"

    def apply(self, *operands: Decimal) -> Decimal:
        """Return left raised to right using Decimal arithmetic."""
        try:
            return operands[0] ** operands[1]
        except DecimalException as exc:
            raise EvaluationError(
                f"Cannot raise {operands[0]} to the power {operands[1]}."
            ) from exc


class UnaryNegationStrategy(OperatorStrategy):
    """Negate one Decimal operand; the parser emits its internal symbol."""

    symbol, precedence, associativity, arity = "u-", 3, "right", 1

    def apply(self, *operands: Decimal) -> Decimal:
        """Return the negated operand."""
        return -operands[0]


class OperationRegistry:
    """Validate, register, and resolve operation strategy instances."""

    def __init__(self) -> None:
        self._strategies: dict[str, OperatorStrategy] = {}

    @classmethod
    def with_defaults(cls) -> OperationRegistry:
        """Create a registry containing all calculator-supported operators."""
        registry = cls()
        for strategy in (
            AdditionStrategy(),
            SubtractionStrategy(),
            MultiplicationStrategy(),
            DivisionStrategy(),
            ExponentiationStrategy(),
            UnaryNegationStrategy(),
        ):
            registry.register(strategy)
        return registry

    def register(self, strategy: OperatorStrategy, *, replace: bool = False) -> None:
        """Register a validated strategy, optionally replacing the same symbol."""
        if not isinstance(strategy, OperatorStrategy):
            raise ConfigurationError("Operator strategy must implement OperatorStrategy.")
        symbol = getattr(strategy, "symbol", None)
        is_internal_negation = isinstance(strategy, UnaryNegationStrategy)
        if (
            not isinstance(symbol, str)
            or not symbol
            or (symbol == "u-" and not is_internal_negation)
            or any(character.isspace() or character.isdigit() or character in ".()" for character in symbol)
        ):
            raise ConfigurationError(f"Invalid operator symbol: {symbol!r}.")
        if getattr(strategy, "arity", None) != (1 if is_internal_negation else 2):
            raise ConfigurationError("Custom operator strategies must be binary.")
        if not isinstance(getattr(strategy, "precedence", None), int) or strategy.precedence < 1:
            raise ConfigurationError("Operator precedence must be a positive integer.")
        if getattr(strategy, "associativity", None) not in {"left", "right"}:
            raise ConfigurationError("Operator associativity must be 'left' or 'right'.")
        if symbol in self._strategies and not replace:
            raise ConfigurationError(f"Operator {symbol!r} is already registered.")
        self._strategies[symbol] = strategy

    def get(self, symbol: str) -> OperatorStrategy:
        """Return a registered strategy or raise a domain exception."""
        try:
            return self._strategies[symbol]
        except KeyError as exc:
            raise UnsupportedOperatorError(f"Unsupported operator: {symbol!r}.") from exc

    @property
    def strategies(self) -> Mapping[str, OperatorStrategy]:
        """Return a read-only view of registered strategies."""
        return MappingProxyType(self._strategies)

    @property
    def expression_symbols(self) -> tuple[str, ...]:
        """Return user-facing symbols longest-first for deterministic tokenization."""
        return tuple(
            sorted((symbol for symbol in self._strategies if symbol != "u-"), key=len, reverse=True)
        )
