"""Strategy implementations for supported arithmetic operations."""

from __future__ import annotations

from abc import ABC, abstractmethod

CalculatorNumber = int | float


class OperationStrategy(ABC):
    """Interface for a binary arithmetic operation."""

    @abstractmethod
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        """Calculate a result from two validated operands."""


class AddStrategy(OperationStrategy):
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        return left + right


class SubtractStrategy(OperationStrategy):
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        return left - right


class MultiplyStrategy(OperationStrategy):
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        return left * right


class DivideStrategy(OperationStrategy):
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        if right == 0:
            raise ZeroDivisionError("division by zero is not allowed")
        return left / right


class PowerStrategy(OperationStrategy):
    def execute(self, left: CalculatorNumber, right: CalculatorNumber) -> CalculatorNumber:
        return left**right


def default_strategies() -> dict[str, OperationStrategy]:
    """Return a fresh registry of the standard calculator operations."""

    return {
        "add": AddStrategy(),
        "subtract": SubtractStrategy(),
        "multiply": MultiplyStrategy(),
        "divide": DivideStrategy(),
        "power": PowerStrategy(),
    }
