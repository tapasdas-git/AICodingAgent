"""Strategy-based arithmetic execution with successful-result history."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from .schemas import CalculationRequest, CalculationResult, OperationType


@runtime_checkable
class OperationStrategy(Protocol):
    """Interface implemented by each binary arithmetic strategy."""

    def execute(self, operand1: float, operand2: float) -> float:
        """Apply the strategy to two finite operands and return its result."""


class _AddStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        """Return the sum of both operands."""

        return operand1 + operand2


class _SubtractStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        """Subtract the second operand from the first."""

        return operand1 - operand2


class _MultiplyStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        """Return the product of both operands."""

        return operand1 * operand2


class _DivideStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        """Divide the first operand by a nonzero second operand."""

        if operand2 == 0:
            raise ZeroDivisionError("cannot divide by zero")
        return operand1 / operand2


class _PowerStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        """Raise the first operand to the power of the second."""

        return operand1**operand2


def _default_strategies() -> dict[OperationType, OperationStrategy]:
    return {
        OperationType.ADD: _AddStrategy(),
        OperationType.SUBTRACT: _SubtractStrategy(),
        OperationType.MULTIPLY: _MultiplyStrategy(),
        OperationType.DIVIDE: _DivideStrategy(),
        OperationType.POWER: _PowerStrategy(),
    }


class CalculatorEngine:
    """Perform validated calculations and retain successful results in order.

    A copy of the strategy mapping is frozen during construction so callers cannot
    replace an operation after configuration has been validated. Failed operations
    are intentionally excluded from history, preserving an auditable success log.
    """

    def __init__(
        self,
        strategies: Mapping[OperationType, OperationStrategy] | None = None,
    ) -> None:
        configured = (
            dict(strategies) if strategies is not None else _default_strategies()
        )
        if set(configured) != set(OperationType) or not all(
            isinstance(operation, OperationType) for operation in configured
        ):
            raise ValueError(
                "strategies must define every supported operation exactly once"
            )
        if not all(
            callable(getattr(strategy, "execute", None))
            for strategy in configured.values()
        ):
            raise TypeError("every strategy must provide a callable execute method")

        self._strategies = MappingProxyType(configured)
        self._history: list[CalculationResult] = []

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        """Execute a validated request and append only a valid, finite result."""

        if not isinstance(request, CalculationRequest):
            raise TypeError("request must be a CalculationRequest")

        raw_result = self._strategies[request.operation].execute(
            request.operand1,
            request.operand2,
        )
        try:
            calculation = CalculationResult(
                operation=request.operation,
                operand1=request.operand1,
                operand2=request.operand2,
                result=raw_result,
            )
        except ValidationError as exc:
            raise ArithmeticError(
                "operation produced an invalid or non-finite result"
            ) from exc

        self._history.append(calculation)
        return calculation

    def get_history(self) -> list[CalculationResult]:
        """Return a snapshot of successful calculations in execution order."""

        return self._history.copy()


def create_calculator_engine(
    strategies: Mapping[OperationType, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create the public calculator entry point with validated dependencies."""

    return CalculatorEngine(strategies=strategies)
