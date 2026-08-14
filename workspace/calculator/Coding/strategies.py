"""Arithmetic strategies used by the calculator engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
import math

from .schemas import Operation


class OperationStrategy(ABC):
    """Interface implemented by calculator operation strategies."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Return the result for two validated finite operands."""


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
        except OverflowError as exc:
            raise ValueError("calculation result must be finite") from exc
        if isinstance(result, complex):
            raise ValueError("calculation result must be a real number")
        return result


DEFAULT_STRATEGIES: dict[Operation, OperationStrategy] = {
    Operation.ADD: AddStrategy(),
    Operation.SUBTRACT: SubtractStrategy(),
    Operation.MULTIPLY: MultiplyStrategy(),
    Operation.DIVIDE: DivideStrategy(),
    Operation.POWER: PowerStrategy(),
}


def ensure_finite(result: float) -> float:
    value = float(result)
    if not math.isfinite(value):
        raise ValueError("calculation result must be finite")
    return value
