"""Strategy-driven calculator engine with bounded history."""

from __future__ import annotations

import math
from collections.abc import Mapping
from threading import RLock

from .operations import (
    AddStrategy,
    DivideStrategy,
    MultiplyStrategy,
    OperationStrategy,
    PowerStrategy,
    SubtractStrategy,
)
from .schemas import CalculationRecord, CalculationRequest, CalculatorConfig, Operation


def _standard_strategies() -> dict[Operation, OperationStrategy]:
    return {
        Operation.ADD: AddStrategy(),
        Operation.SUBTRACT: SubtractStrategy(),
        Operation.MULTIPLY: MultiplyStrategy(),
        Operation.DIVIDE: DivideStrategy(),
        Operation.POWER: PowerStrategy(),
    }


def _validate_config(config: CalculatorConfig | Mapping[str, object] | None) -> CalculatorConfig:
    """Validate configuration even when passed an existing model instance."""
    candidate = config.model_dump() if isinstance(config, CalculatorConfig) else (config or {})
    return CalculatorConfig.model_validate(candidate)


def _validate_strategies(
    strategies: Mapping[Operation | str, OperationStrategy] | None,
) -> dict[Operation, OperationStrategy]:
    """Return validated standard strategies with normalized overrides."""
    if strategies is not None and not isinstance(strategies, Mapping):
        raise TypeError("strategies must be a mapping")

    configured: dict[Operation, OperationStrategy] = {}
    for operation, strategy in (*_standard_strategies().items(), *((strategies or {}).items())):
        try:
            normalized_operation = Operation(operation)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported strategy operation: {operation}") from exc
        if not isinstance(strategy, OperationStrategy):
            raise TypeError("strategies must implement OperationStrategy")
        configured[normalized_operation] = strategy
    return configured


class CalculatorEngine:
    """Perform validated calculations and retain successful results in order."""

    def __init__(
        self,
        config: CalculatorConfig | Mapping[str, object] | None = None,
        strategies: Mapping[Operation | str, OperationStrategy] | None = None,
    ) -> None:
        self._config = _validate_config(config)
        self._strategies = _validate_strategies(strategies)
        self._history: list[CalculationRecord] = []
        self._next_sequence = 1
        self._lock = RLock()

    @property
    def history(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable snapshot of successful calculations."""
        with self._lock:
            return tuple(self._history)

    def calculate(self, operation: Operation | str, left: int | float, right: int | float) -> float:
        """Validate and execute one calculation.

        Validation and operation errors are propagated to the caller, and failed
        calculations are never added to history.
        """
        request = CalculationRequest(operation=operation, left=left, right=right)
        with self._lock:
            strategy = self._strategies.get(request.operation)
            if strategy is None:
                raise ValueError(f"no strategy configured for operation: {request.operation.value}")

            try:
                result = strategy.execute(request.left, request.right)
            except (OverflowError, ValueError) as exc:
                raise ValueError(f"operation {request.operation.value} could not be completed") from exc

            if isinstance(result, bool) or not isinstance(result, (int, float)) or not math.isfinite(result):
                raise ValueError(f"operation {request.operation.value} produced a non-finite real result")

            record = CalculationRecord(
                sequence=self._next_sequence,
                operation=request.operation,
                left=request.left,
                right=request.right,
                result=result,
            )
            self._next_sequence += 1
            self._history.append(record)
            if len(self._history) > self._config.max_history:
                del self._history[0]
            return result

    def clear_history(self) -> None:
        """Remove all stored records without changing sequence identity."""
        with self._lock:
            self._history.clear()


def create_calculator(
    config: CalculatorConfig | Mapping[str, object] | None = None,
    strategies: Mapping[Operation | str, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create a calculator with validated configuration and injectable strategies."""
    return CalculatorEngine(config=config, strategies=strategies)


__all__ = ["CalculatorEngine", "create_calculator"]
