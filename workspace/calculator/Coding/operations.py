"""Arithmetic strategies used by the calculator engine."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import is_finite_number

Number = int | float


class OperationStrategy(ABC):
    """Interface implemented by binary operation strategies."""

    @abstractmethod
    def execute(self, left: Number, right: Number) -> Number:
        """Return the result for two validated operands."""


class AddStrategy(OperationStrategy):
    def execute(self, left: Number, right: Number) -> Number:
        return left + right


class SubtractStrategy(OperationStrategy):
    def execute(self, left: Number, right: Number) -> Number:
        return left - right


class MultiplyStrategy(OperationStrategy):
    def execute(self, left: Number, right: Number) -> Number:
        return left * right


class DivideStrategy(OperationStrategy):
    def execute(self, left: Number, right: Number) -> Number:
        if right == 0:
            raise ZeroDivisionError("cannot divide by zero")
        return left / right


class PowerStrategy(OperationStrategy):
    def execute(self, left: Number, right: Number) -> Number:
        try:
            result = left**right
        except OverflowError as error:
            raise ValueError("operation must produce a finite real number") from error
        if not is_finite_number(result):
            raise ValueError("operation must produce a finite real number")
        return result
