"""Strategy-based arithmetic engine with in-memory calculation history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping
from decimal import Decimal, DecimalException
from types import MappingProxyType

from pydantic import ValidationError

from .schemas import CalculationRequest, CalculationResult, OperationType


class OperationStrategy(ABC):
    """Interface for one deterministic binary arithmetic operation."""

    @abstractmethod
    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Apply the operation and return its result."""


class AdditionStrategy(OperationStrategy):
    """Add the second operand to the first."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return the sum of both operands."""

        return operand1 + operand2


class SubtractionStrategy(OperationStrategy):
    """Subtract the second operand from the first."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return the difference between both operands."""

        return operand1 - operand2


class MultiplicationStrategy(OperationStrategy):
    """Multiply both operands."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return the product of both operands."""

        return operand1 * operand2


class DivisionStrategy(OperationStrategy):
    """Divide the first operand by the second."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return the quotient, rejecting a zero divisor explicitly."""

        if operand2 == 0:
            raise ZeroDivisionError("division by zero is not allowed")
        return operand1 / operand2


class PowerStrategy(OperationStrategy):
    """Raise the first operand to the power of the second."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return ``operand1`` raised to ``operand2``."""

        return operand1**operand2


DEFAULT_STRATEGIES: Mapping[OperationType, OperationStrategy] = MappingProxyType(
    {
        OperationType.ADD: AdditionStrategy(),
        OperationType.SUBTRACT: SubtractionStrategy(),
        OperationType.MULTIPLY: MultiplicationStrategy(),
        OperationType.DIVIDE: DivisionStrategy(),
        OperationType.POWER: PowerStrategy(),
    }
)


class CalculatorEngine:
    """Validate calculations, dispatch strategies, and retain successful results."""

    def __init__(
        self,
        strategies: Mapping[OperationType | str, OperationStrategy] | None = None,
        *,
        history_limit: int = 1_000,
    ) -> None:
        """Create an engine with complete strategies and bounded history storage."""

        if isinstance(history_limit, bool) or not isinstance(history_limit, int):
            raise TypeError("history_limit must be an integer")
        if history_limit <= 0:
            raise ValueError("history_limit must be greater than zero")

        normalized: dict[OperationType, OperationStrategy] = {}
        selected_strategies = DEFAULT_STRATEGIES if strategies is None else strategies
        for operation, strategy in selected_strategies.items():
            operation_type = OperationType(operation)
            if not isinstance(strategy, OperationStrategy):
                raise TypeError(
                    f"strategy for {operation_type.value!r} must implement "
                    "OperationStrategy"
                )
            normalized[operation_type] = strategy

        missing = set(OperationType).difference(normalized)
        if missing:
            names = ", ".join(sorted(operation.value for operation in missing))
            raise ValueError(f"missing strategies for operations: {names}")

        self._strategies = MappingProxyType(normalized)
        self._history: deque[CalculationResult] = deque(maxlen=history_limit)

    def calculate(
        self,
        request: CalculationRequest | Mapping[str, object] | OperationType | str,
        operand1: object | None = None,
        operand2: object | None = None,
    ) -> CalculationResult:
        """Perform a validated calculation and append a successful result to history.

        Callers may supply a request model, a request-shaped mapping, or the
        convenience form ``calculate(operation, operand1, operand2)``.
        """

        if isinstance(request, CalculationRequest):
            if operand1 is not None or operand2 is not None:
                raise TypeError("operands cannot accompany a CalculationRequest")
            validated = request
        elif isinstance(request, Mapping):
            if operand1 is not None or operand2 is not None:
                raise TypeError("operands cannot accompany a request mapping")
            validated = CalculationRequest.model_validate(request)
        else:
            if operand1 is None or operand2 is None:
                raise TypeError("both operands are required")
            validated = CalculationRequest.model_validate(
                {
                    "operation": request,
                    "operand1": operand1,
                    "operand2": operand2,
                }
            )

        strategy = self._strategies[validated.operation]
        try:
            raw_result = strategy.execute(validated.operand1, validated.operand2)
            result = CalculationResult(
                operation=validated.operation,
                operand1=validated.operand1,
                operand2=validated.operand2,
                result=raw_result,
            )
        except ZeroDivisionError:
            raise
        except (DecimalException, ValidationError) as error:
            raise ArithmeticError("operation did not produce a finite result") from error

        self._history.append(result)
        return result

    def get_history(self) -> tuple[CalculationResult, ...]:
        """Return an immutable snapshot of successful results in execution order."""

        return tuple(self._history)

    @property
    def history(self) -> tuple[CalculationResult, ...]:
        """Return an immutable snapshot of successful calculation history."""

        return self.get_history()

    def clear_history(self) -> None:
        """Remove all calculation history from this engine instance."""

        self._history.clear()


def create_calculator(
    strategies: Mapping[OperationType | str, OperationStrategy] | None = None,
    *,
    history_limit: int = 1_000,
) -> CalculatorEngine:
    """Create the public calculator with injectable strategies and bounded history."""

    return CalculatorEngine(strategies, history_limit=history_limit)
