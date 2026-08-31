"""Strategy-based arithmetic calculator with in-memory history."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .schemas import CalculationRequest, CalculationResult, OperationType


@runtime_checkable
class OperationStrategy(Protocol):
    """Contract implemented by arithmetic operation strategies."""

    def execute(self, operand1: float, operand2: float) -> float:
        """Return the result of applying this strategy to two operands."""


class AddStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 + operand2


class SubtractStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 - operand2


class MultiplyStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 * operand2


class DivideStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        if operand2 == 0:
            raise ZeroDivisionError("division by zero is not allowed")
        return operand1 / operand2


class PowerStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        try:
            result = operand1**operand2
        except OverflowError as exc:
            raise ValueError("power result is outside the supported numeric range") from exc
        if isinstance(result, complex):
            raise ValueError("power operation must produce a real number")
        return result


class CalculatorEngine:
    """Execute validated calculations through an injected strategy allowlist."""

    def __init__(self, strategies: Mapping[OperationType, OperationStrategy]):
        validated: dict[OperationType, OperationStrategy] = {}
        for operation, strategy in strategies.items():
            operation_type = OperationType(operation)
            if not isinstance(strategy, OperationStrategy) or not callable(strategy.execute):
                raise TypeError(f"strategy for {operation_type.value!r} must implement execute()")
            validated[operation_type] = strategy
        if not validated:
            raise ValueError("at least one operation strategy is required")
        self._strategies = validated
        self._history: list[CalculationResult] = []

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        """Execute a request and append only a successful result to history."""

        if not isinstance(request, CalculationRequest):
            raise TypeError("request must be a CalculationRequest")
        strategy = self._strategies.get(request.operation)
        if strategy is None:
            raise ValueError(f"operation {request.operation.value!r} is not enabled")
        value = strategy.execute(request.operand1, request.operand2)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("operation strategy must return a real number")
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("calculation result must be finite")
        calculation = CalculationResult(
            operation=request.operation,
            operand1=request.operand1,
            operand2=request.operand2,
            result=numeric_value,
        )
        self._history.append(calculation)
        return calculation

    def get_history(self) -> list[CalculationResult]:
        """Return a snapshot so callers cannot mutate the engine's history list."""

        return list(self._history)

    def clear_history(self) -> None:
        """Remove all stored calculation results."""

        self._history.clear()


def create_calculator_engine(
    *, strategies: Mapping[OperationType, OperationStrategy] | None = None
) -> CalculatorEngine:
    """Create an engine with standard strategies or an injected allowlist."""

    standard_strategies: Mapping[OperationType, OperationStrategy] = {
        OperationType.ADD: AddStrategy(),
        OperationType.SUBTRACT: SubtractStrategy(),
        OperationType.MULTIPLY: MultiplyStrategy(),
        OperationType.DIVIDE: DivideStrategy(),
        OperationType.POWER: PowerStrategy(),
    }
    return CalculatorEngine(standard_strategies if strategies is None else strategies)
