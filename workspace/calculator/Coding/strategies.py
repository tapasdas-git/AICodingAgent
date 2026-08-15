"""Arithmetic strategies used by :mod:`engine`."""

from __future__ import annotations

from abc import ABC, abstractmethod


class OperationStrategy(ABC):
    """Interface implemented by binary arithmetic operations."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Return the result for the two operands."""


class AddStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left + right


class SubtractStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left - right


class MultiplyStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left * right


class DivideStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        if right == 0:
            raise ZeroDivisionError("division by zero is not allowed")
        return left / right


class PowerStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left**right


def default_strategies() -> dict[str, OperationStrategy]:
    """Create a fresh standard strategy registry."""

    return {
        "add": AddStrategy(),
        "subtract": SubtractStrategy(),
        "multiply": MultiplyStrategy(),
        "divide": DivideStrategy(),
        "power": PowerStrategy(),
    }
