"""Extensible arithmetic operation strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow
from typing import Literal

from .exceptions import CalculatorError, DivisionByZeroError, EvaluationError

Associativity = Literal["left", "right"]


class OperatorStrategy(ABC):
    """Contract implemented by each binary arithmetic operator."""

    symbol: str
    precedence: int
    associativity: Associativity = "left"

    @abstractmethod
    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the result of applying the operator to two operands."""


class AdditionStrategy(OperatorStrategy):
    """Add two decimal operands."""

    symbol = "+"
    precedence = 10

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left + right``."""
        return left + right


class SubtractionStrategy(OperatorStrategy):
    """Subtract the right decimal operand from the left one."""

    symbol = "-"
    precedence = 10

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left - right``."""
        return left - right


class MultiplicationStrategy(OperatorStrategy):
    """Multiply two decimal operands."""

    symbol = "*"
    precedence = 20

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left * right``."""
        return left * right


class DivisionStrategy(OperatorStrategy):
    """Divide the left decimal operand by the right one."""

    symbol = "/"
    precedence = 20

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left / right`` or raise a domain division error."""
        if right == 0:
            raise DivisionByZeroError("Cannot divide by zero.")
        return left / right


class ExponentiationStrategy(OperatorStrategy):
    """Raise the left decimal operand to the right operand's power."""

    symbol = "^"
    precedence = 30
    associativity: Associativity = "right"

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return ``left ** right`` with Decimal arithmetic."""
        return left**right


def default_strategies() -> tuple[OperatorStrategy, ...]:
    """Return new instances of all built-in operator strategies."""
    return (
        AdditionStrategy(),
        SubtractionStrategy(),
        MultiplicationStrategy(),
        DivisionStrategy(),
        ExponentiationStrategy(),
    )


def apply_safely(
    strategy: OperatorStrategy, left: Decimal, right: Decimal
) -> Decimal:
    """Apply a strategy while translating Decimal failures to safe errors."""
    try:
        result = strategy.apply(left, right)
    except CalculatorError:
        raise
    except (ArithmeticError, DivisionByZero, InvalidOperation, Overflow) as exc:
        raise EvaluationError(
            f"Operator {strategy.symbol!r} could not evaluate its operands."
        ) from exc
    except Exception as exc:
        # Injected strategies are an extension boundary; their implementation
        # details must not leak through the calculator's public error contract.
        raise EvaluationError(
            f"Operator {strategy.symbol!r} failed while evaluating its operands."
        ) from exc
    if not isinstance(result, Decimal):
        raise EvaluationError(
            f"Operator {strategy.symbol!r} returned a non-Decimal result."
        )
    if not result.is_finite():
        raise EvaluationError(
            f"Operator {strategy.symbol!r} produced a non-finite result."
        )
    return result
