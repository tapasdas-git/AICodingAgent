"""Thread-safe calculator engine and its public factory."""

from __future__ import annotations

import math
from threading import RLock
from typing import Mapping

from .operations import (
    AddStrategy,
    DivideStrategy,
    MultiplyStrategy,
    OperationStrategy,
    PowerStrategy,
    SubtractStrategy,
)
from .schemas import CalculationRecord, CalculationRequest, Operation


DEFAULT_STRATEGIES: Mapping[Operation, OperationStrategy] = {
    Operation.ADD: AddStrategy(),
    Operation.SUBTRACT: SubtractStrategy(),
    Operation.MULTIPLY: MultiplyStrategy(),
    Operation.DIVIDE: DivideStrategy(),
    Operation.POWER: PowerStrategy(),
}


class CalculatorEngine:
    """Perform allowlisted arithmetic operations and retain their history."""

    def __init__(self, strategies: Mapping[Operation, OperationStrategy]) -> None:
        if set(strategies) != set(Operation):
            raise ValueError("strategies must define every supported operation exactly once")
        if any(not isinstance(strategy, OperationStrategy) for strategy in strategies.values()):
            raise TypeError("each strategy must implement OperationStrategy")
        self._strategies = dict(strategies)
        self._history: list[CalculationRecord] = []
        self._lock = RLock()

    def calculate(self, operation: Operation | str, left: int | float, right: int | float) -> CalculationRecord:
        request = CalculationRequest(operation=operation, left=left, right=right)
        result = self._strategies[request.operation].execute(request.left, request.right)
        if not math.isfinite(result):
            raise ValueError("calculation result must be finite")
        record = CalculationRecord(**request.model_dump(), result=result)
        with self._lock:
            self._history.append(record)
        return record

    def get_history(self) -> tuple[CalculationRecord, ...]:
        with self._lock:
            return tuple(self._history)

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()


def create_calculator(
    strategies: Mapping[Operation, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create an engine with defaults or a complete injected strategy mapping."""

    return CalculatorEngine(DEFAULT_STRATEGIES if strategies is None else strategies)
