"""Strategy-based arithmetic engine with in-memory history."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from .schemas import CalculationRequest, CalculationResult, OperationType


@runtime_checkable
class OperationStrategy(Protocol):
    """Contract implemented by binary arithmetic strategies."""

    def execute(self, operand1: float, operand2: float) -> float:
        """Return the result of applying an operation to two operands."""


class _AddStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 + operand2


class _SubtractStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 - operand2


class _MultiplyStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        return operand1 * operand2


class _DivideStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
        if operand2 == 0:
            raise ZeroDivisionError("cannot divide by zero")
        return operand1 / operand2


class _PowerStrategy:
    def execute(self, operand1: float, operand2: float) -> float:
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
    """Perform validated calculations and retain successful results in order."""

    def __init__(
        self,
        strategies: Mapping[OperationType, OperationStrategy] | None = None,
    ) -> None:
        configured = dict(strategies) if strategies is not None else _default_strategies()
        expected = set(OperationType)
        if set(configured) != expected:
            raise ValueError("strategies must define every supported operation exactly once")
        if not all(
            isinstance(strategy, OperationStrategy)
            and callable(getattr(strategy, "execute", None))
            for strategy in configured.values()
        ):
            raise TypeError("every strategy must provide a callable execute method")

        self._strategies = MappingProxyType(configured)
        self._history: list[CalculationResult] = []

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        """Execute a validated request and record only a successful result."""

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
            raise ArithmeticError("operation produced a non-finite result") from exc
        self._history.append(calculation)
        return calculation

    def get_history(self) -> list[CalculationResult]:
        """Return a snapshot of successful calculations in execution order."""

        return self._history.copy()


def create_calculator_engine(
    strategies: Mapping[OperationType, OperationStrategy] | None = None,
) -> CalculatorEngine:
    """Create an engine with validated, optionally injected strategies."""

    return CalculatorEngine(strategies=strategies)
