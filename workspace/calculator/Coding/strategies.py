"""Strategy implementations for the calculator's arithmetic operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from numbers import Real


class OperationStrategy(ABC):
    """Interface for an injectable binary arithmetic operation."""

    @abstractmethod
    def execute(self, left: Real, right: Real) -> Real:
        """Return the result of applying the strategy to two operands."""


class AddStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        return left + right


class SubtractStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        return left - right


class MultiplyStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        return left * right


class DivideStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        if right == 0:
            raise ZeroDivisionError("division by zero is not allowed")
        return left / right


class PowerStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        return left**right


def default_strategies() -> dict[str, OperationStrategy]:
    """Return fresh standard strategies for a calculator instance."""

    return {
        "add": AddStrategy(),
        "subtract": SubtractStrategy(),
        "multiply": MultiplyStrategy(),
        "divide": DivideStrategy(),
        "power": PowerStrategy(),
    }
