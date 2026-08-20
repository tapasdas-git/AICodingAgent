"""Strategy implementations for standard arithmetic operations."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from .models import OperationName


class OperationStrategy(ABC):
    """Interface implemented by every binary calculator operation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the normalized name used to dispatch this strategy."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Execute the operation for two validated operands."""


class AddStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return OperationName.ADD.value

    def execute(self, left: float, right: float) -> float:
        return left + right


class SubtractStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return OperationName.SUBTRACT.value

    def execute(self, left: float, right: float) -> float:
        return left - right


class MultiplyStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return OperationName.MULTIPLY.value

    def execute(self, left: float, right: float) -> float:
        return left * right


class DivideStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return OperationName.DIVIDE.value

    def execute(self, left: float, right: float) -> float:
        if right == 0:
            raise ZeroDivisionError("cannot divide by zero")
        return left / right


class PowerStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return OperationName.POWER.value

    def execute(self, left: float, right: float) -> float:
        return math.pow(left, right)


def standard_strategies() -> tuple[OperationStrategy, ...]:
    """Create a fresh set of the five built-in strategies."""

    return (
        AddStrategy(),
        SubtractStrategy(),
        MultiplyStrategy(),
        DivideStrategy(),
        PowerStrategy(),
    )
