"""Calculator entry point with injectable arithmetic strategies."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from .operations import (
    AddStrategy,
    DivideStrategy,
    MultiplyStrategy,
    OperationStrategy,
    PowerStrategy,
    SubtractStrategy,
)
from .schemas import CalculationRecord, CalculationRequest, Operation, is_finite_number

Number = int | float


def _standard_strategies() -> dict[Operation, OperationStrategy]:
    return {
        Operation.ADD: AddStrategy(),
        Operation.SUBTRACT: SubtractStrategy(),
        Operation.MULTIPLY: MultiplyStrategy(),
        Operation.DIVIDE: DivideStrategy(),
        Operation.POWER: PowerStrategy(),
    }


class CalculatorEngine:
    """Perform validated calculations and retain successful results."""

    def __init__(self, strategies: Mapping[Operation, OperationStrategy]) -> None:
        if not strategies:
            raise ValueError("at least one operation strategy is required")
        invalid = [strategy for strategy in strategies.values() if not isinstance(strategy, OperationStrategy)]
        if invalid:
            raise TypeError("every strategy must implement OperationStrategy")
        self._strategies = dict(strategies)
        self._history: list[CalculationRecord] = []

    def calculate(self, operation: Operation | str, left: Number, right: Number) -> Number:
        """Execute an operation and append a record only when it succeeds."""
        try:
            request = CalculationRequest(operation=operation, left=left, right=right)
        except ValidationError as error:
            raise ValueError(f"invalid calculation request: {error.errors()[0]['msg']}") from error

        strategy = self._strategies.get(request.operation)
        if strategy is None:
            raise ValueError(f"operation is not configured: {request.operation.value}")
        try:
            result = strategy.execute(request.left, request.right)
        except OverflowError as error:
            raise ValueError("operation must produce a finite real number") from error
        if isinstance(result, bool) or isinstance(result, complex) or not isinstance(result, (int, float)):
            raise TypeError("operation strategy must return a real number")
        if not is_finite_number(result):
            raise ValueError("operation must produce a finite real number")

        self._history.append(
            CalculationRecord(
                operation=request.operation,
                left=request.left,
                right=request.right,
                result=result,
            )
        )
        return result

    def get_history(self) -> list[CalculationRecord]:
        """Return a copy of successful calculations in execution order."""
        return list(self._history)

    def clear_history(self) -> None:
        """Remove all calculation records."""
        self._history.clear()


def create_calculator(
    strategies: Mapping[Operation, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create a calculator with standard or explicitly injected strategies."""
    return CalculatorEngine(_standard_strategies() if strategies is None else strategies)
