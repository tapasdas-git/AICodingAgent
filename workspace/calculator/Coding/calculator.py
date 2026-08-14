from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from schemas import CalculationRecord, CalculationRequest, OperationName


class OperationStrategy(ABC):
    """Strategy interface for a binary arithmetic operation."""

    @abstractmethod
    def execute(self, left: float, right: float) -> float:
        """Return the result of applying the operation to two operands."""


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
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("power operation has no finite real result") from exc
        if isinstance(result, complex) or not math.isfinite(result):
            raise ValueError("power operation has no finite real result")
        return result


REQUIRED_OPERATIONS = frozenset({"add", "subtract", "multiply", "divide", "power"})

DEFAULT_STRATEGIES: Mapping[OperationName, OperationStrategy] = MappingProxyType({
    "add": AddStrategy(),
    "subtract": SubtractStrategy(),
    "multiply": MultiplyStrategy(),
    "divide": DivideStrategy(),
    "power": PowerStrategy(),
})

_RESULT_ADAPTER = TypeAdapter(Annotated[float, Field(strict=True, allow_inf_nan=False)])


class CalculatorEngine:
    """Validated calculator entry point with successful-operation history."""

    def __init__(self, strategies: Mapping[OperationName, OperationStrategy] | None = None) -> None:
        selected = DEFAULT_STRATEGIES if strategies is None else strategies
        missing = REQUIRED_OPERATIONS.difference(selected)
        if missing:
            raise ValueError(f"missing operation strategies: {', '.join(sorted(missing))}")
        if any(not isinstance(strategy, OperationStrategy) for strategy in selected.values()):
            raise TypeError("all strategies must implement OperationStrategy")
        self._strategies = dict(selected)
        self._history: list[CalculationRecord] = []

    def calculate(self, operation: str, left: float, right: float) -> float:
        try:
            request = CalculationRequest(operation=operation, left=left, right=right)
        except ValidationError as exc:
            raise ValueError(f"invalid calculation request: {exc.errors()[0]['msg']}") from exc

        raw_result = self._strategies[request.operation].execute(request.left, request.right)
        try:
            result = _RESULT_ADAPTER.validate_python(raw_result)
        except ValidationError as exc:
            raise ValueError("calculation result must be finite real number") from exc
        self._history.append(CalculationRecord(**request.model_dump(), result=result))
        return result

    def get_history(self) -> tuple[CalculationRecord, ...]:
        return tuple(self._history)

    def clear_history(self) -> None:
        self._history.clear()


def create_calculator(
    strategies: Mapping[OperationName, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create a calculator with validated, optionally injectable strategies."""

    return CalculatorEngine(strategies)
