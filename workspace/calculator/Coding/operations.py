"""Arithmetic strategies for the calculator engine."""

from __future__ import annotations

from abc import ABC, abstractmethod


class OperationStrategy(ABC):
    """Interface implemented by every binary arithmetic operation."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Execute the operation for two validated finite operands."""


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
            raise ZeroDivisionError("cannot divide by zero")
        return left / right


class PowerStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left**right
