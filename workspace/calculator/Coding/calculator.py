"""Thread-safe calculator engine and its public factory."""

from __future__ import annotations

from collections.abc import Mapping
from threading import RLock

from pydantic import TypeAdapter

from .schemas import CalculationRecord, CalculationRequest, Operation
from .strategies import DEFAULT_STRATEGIES, OperationStrategy, ensure_finite


class CalculatorEngine:
    """Perform validated calculations and retain bounded result history."""

    def __init__(
        self,
        *,
        max_history: int = 100,
        strategies: Mapping[Operation, OperationStrategy] | None = None,
    ) -> None:
        if isinstance(max_history, bool) or not isinstance(max_history, int) or max_history < 1:
            raise ValueError("max_history must be a positive integer")
        selected = dict(DEFAULT_STRATEGIES if strategies is None else strategies)
        required = set(Operation)
        if set(selected) != required:
            raise ValueError("strategies must define every supported operation exactly once")
        if any(not isinstance(strategy, OperationStrategy) for strategy in selected.values()):
            raise TypeError("every strategy must implement OperationStrategy")

        self._max_history = max_history
        self._strategies = selected
        self._history: list[CalculationRecord] = []
        self._lock = RLock()

    def calculate(
        self,
        operation: Operation | str,
        left: float,
        right: float,
    ) -> float:
        request = CalculationRequest(operation=operation, left=left, right=right)
        result = ensure_finite(self._strategies[request.operation].execute(request.left, request.right))
        record = CalculationRecord(**request.model_dump(), result=result)
        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                del self._history[: -self._max_history]
        return result

    def get_history(self) -> tuple[CalculationRecord, ...]:
        with self._lock:
            return tuple(self._history)

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()


def create_calculator(
    *,
    max_history: int = 100,
    strategies: Mapping[Operation, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create a calculator with validated configuration and optional strategies."""

    TypeAdapter(int).validate_python(max_history, strict=True)
    return CalculatorEngine(max_history=max_history, strategies=strategies)
