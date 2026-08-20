"""Thread-safe calculator engine with validated requests and bounded history."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Mapping
from threading import RLock
from typing import Any

from .models import CalculationRecord, CalculationRequest, CalculatorConfig
from .operations import OperationStrategy, standard_strategies


class CalculatorError(Exception):
    """Base class for errors raised while dispatching a calculation."""


class UnknownOperationError(CalculatorError, ValueError):
    """Raised when no registered strategy matches a requested operation."""


class InvalidStrategyError(CalculatorError, ValueError):
    """Raised when injected operation strategies do not satisfy the contract."""


class CalculationError(CalculatorError, ArithmeticError):
    """Raised when an operation cannot produce a finite real result."""


class DivisionByZeroError(CalculationError, ZeroDivisionError):
    """Raised for division with a zero divisor."""


class CalculatorEngine:
    """Main entry point for calculations and successful-result history."""

    def __init__(
        self,
        config: CalculatorConfig | Mapping[str, Any] | None = None,
        *,
        strategies: Iterable[OperationStrategy] | None = None,
    ) -> None:
        self.config = CalculatorConfig.model_validate(config or {})
        selected = standard_strategies() if strategies is None else tuple(strategies)
        self._strategies = self._validate_strategies(selected)
        self._history: deque[CalculationRecord] = deque(maxlen=self.config.history_limit)
        self._next_sequence = 1
        self._lock = RLock()

    @staticmethod
    def _validate_strategies(strategies: Iterable[OperationStrategy]) -> dict[str, OperationStrategy]:
        registered: dict[str, OperationStrategy] = {}
        for strategy in strategies:
            if not isinstance(strategy, OperationStrategy):
                raise InvalidStrategyError("each strategy must implement OperationStrategy")
            name = strategy.name
            if not isinstance(name, str) or not name.strip() or name != name.strip().lower():
                raise InvalidStrategyError("strategy names must be non-empty lowercase strings")
            if name in registered:
                raise InvalidStrategyError(f"duplicate strategy name: {name}")
            registered[name] = strategy
        if not registered:
            raise InvalidStrategyError("at least one operation strategy is required")
        return registered

    @property
    def available_operations(self) -> tuple[str, ...]:
        """Return registered operation names in deterministic insertion order."""

        return tuple(self._strategies)

    @property
    def history(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable snapshot of successful calculation history."""

        with self._lock:
            return tuple(self._history)

    def calculate(self, operation: str, left: Any, right: Any) -> float:
        """Validate and execute an operation, recording it only on success."""

        request = CalculationRequest(operation=operation, left=left, right=right)
        with self._lock:
            strategy = self._strategies.get(request.operation)
            if strategy is None:
                raise UnknownOperationError(f"unknown operation: {request.operation}")
            try:
                result = float(strategy.execute(request.left, request.right))
            except ZeroDivisionError as exc:
                raise DivisionByZeroError("cannot divide by zero") from exc
            except (ArithmeticError, OverflowError, TypeError, ValueError) as exc:
                raise CalculationError(f"operation {request.operation!r} failed: {exc}") from exc
            if not math.isfinite(result):
                raise CalculationError(f"operation {request.operation!r} produced a non-finite result")
            record = CalculationRecord(
                sequence=self._next_sequence,
                operation=request.operation,
                left=request.left,
                right=request.right,
                result=result,
            )
            self._next_sequence += 1
            self._history.append(record)
            return result

    def clear_history(self) -> None:
        """Remove stored records while preserving monotonic sequence numbers."""

        with self._lock:
            self._history.clear()


def create_calculator_engine(
    config: CalculatorConfig | Mapping[str, Any] | None = None,
    *,
    strategies: Iterable[OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Public factory for a configured engine with injectable strategies."""

    return CalculatorEngine(config, strategies=strategies)
