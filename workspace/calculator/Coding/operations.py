"""Arithmetic strategies used by the calculator engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
import math


class OperationStrategy(ABC):
    """Interface implemented by arithmetic operation strategies."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Return the result for two validated operands."""


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
        try:
            result = left**right
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("power operation is outside the supported real range") from exc
        if isinstance(result, complex) or not math.isfinite(result):
            raise ValueError("power operation is outside the supported real range")
        return float(result)
