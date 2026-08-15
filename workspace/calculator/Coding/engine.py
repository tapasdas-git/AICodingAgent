"""Thread-safe modular calculator engine."""

from __future__ import annotations

from collections import deque
from math import isfinite
from numbers import Real
from threading import RLock
from typing import Mapping

from .schemas import CalculationRecord, CalculatorConfig
from .strategies import OperationStrategy, default_strategies


class CalculatorEngine:
    """Perform named operations and retain bounded successful history."""

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
        self._config = validated_config
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
    def _validate_operand(value: Real, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")
        converted = float(value)
        if not isfinite(converted):
            raise ValueError(f"{name} must be finite")
        return converted

    def calculate(self, operation: str, left: Real, right: Real) -> float:
        """Execute an allowlisted strategy and record a successful result."""

        name = self._normalize_operation(operation)
        left_value = self._validate_operand(left, "left")
        right_value = self._validate_operand(right, "right")
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"unsupported operation: {name}")
        result = strategy.execute(left_value, right_value)
        result_value = self._validate_operand(result, "result")
        record = CalculationRecord(
            operation=name,
            left=left_value,
            right=right_value,
            result=result_value,
        )
        with self._lock:
            self._history.append(record)
        return result_value

    def get_history(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable snapshot ordered from oldest to newest."""

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
    """Build the public calculator entry point with validated configuration."""

    validated_config = CalculatorConfig.model_validate({} if config is None else config)
    registry = default_strategies() if strategies is None else strategies
    return CalculatorEngine(validated_config, registry)
