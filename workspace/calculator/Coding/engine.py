"""Thread-safe modular calculator engine."""

from __future__ import annotations

from collections import deque
from numbers import Real
from threading import RLock
from typing import Mapping

from .schemas import CalculationRecord, CalculatorConfig, require_finite_real
from .strategies import OperationStrategy, default_strategies


class CalculatorEngine:
    """Perform allowlisted calculations and retain bounded successful history."""

    def __init__(
        self,
        config: CalculatorConfig | Mapping[str, object],
        strategies: Mapping[str, OperationStrategy],
    ) -> None:
        validated_config = CalculatorConfig.model_validate(config)
        if not strategies:
            raise ValueError("at least one operation strategy is required")

        registry: dict[str, OperationStrategy] = {}
        for name, strategy in strategies.items():
            normalized_name = self._normalize_operation(name)
            if not isinstance(strategy, OperationStrategy):
                raise TypeError(f"strategy for {name!r} must be an OperationStrategy")
            if normalized_name in registry:
                raise ValueError(f"duplicate operation name: {normalized_name}")
            registry[normalized_name] = strategy

        self._strategies = registry
        self._history: deque[CalculationRecord] = deque(maxlen=validated_config.max_history)
        self._lock = RLock()

    @staticmethod
    def _normalize_operation(operation: str) -> str:
        if not isinstance(operation, str):
            raise TypeError("operation must be a string")
        normalized = operation.strip().casefold()
        if not normalized:
            raise ValueError("operation must not be empty")
        return normalized

    @staticmethod
    def _validate_number(value: Real, field_name: str) -> Real:
        return require_finite_real(value, field_name)

    def calculate(self, operation: str, left: Real, right: Real) -> Real:
        """Execute a named strategy and record its successful finite result."""

        operation_name = self._normalize_operation(operation)
        left_value = self._validate_number(left, "left")
        right_value = self._validate_number(right, "right")
        strategy = self._strategies.get(operation_name)
        if strategy is None:
            raise ValueError(f"unsupported operation: {operation_name}")

        result = strategy.execute(left_value, right_value)
        result_value = self._validate_number(result, "result")
        record = CalculationRecord(
            operation=operation_name,
            left=left_value,
            right=right_value,
            result=result_value,
        )
        with self._lock:
            self._history.append(record)
        return result_value

    def get_history(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable history snapshot from oldest to newest."""

        with self._lock:
            return tuple(self._history)

    def clear_history(self) -> None:
        """Remove all calculation records."""

        with self._lock:
            self._history.clear()


def create_calculator(
    config: CalculatorConfig | Mapping[str, object] | None = None,
    *,
    strategies: Mapping[str, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create a calculator with validated configuration and injectable strategies."""

    validated_config = CalculatorConfig.model_validate({} if config is None else config)
    registry = default_strategies() if strategies is None else strategies
    return CalculatorEngine(validated_config, registry)
