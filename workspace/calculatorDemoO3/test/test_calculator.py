"""Acceptance and regression tests for the modular calculator engine."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from workspace.calculatorDemoO3.Coding.engine import (
    DEFAULT_STRATEGIES,
    CalculatorEngine,
    OperationStrategy,
    create_calculator,
)
from workspace.calculatorDemoO3.Coding.schemas import (
    CalculationRequest,
    CalculationResult,
    OperationType,
)


@pytest.mark.parametrize(
    ("operation", "operand1", "operand2", "expected"),
    [
        (OperationType.ADD, "2.1", "3.2", Decimal("5.3")),
        (OperationType.SUBTRACT, 10, 4, Decimal("6")),
        (OperationType.MULTIPLY, "2.5", 4, Decimal("10.0")),
        (OperationType.DIVIDE, 9, 4, Decimal("2.25")),
        (OperationType.POWER, 2, 8, Decimal("256")),
    ],
)
def test_standard_operations_use_validated_requests(
    operation, operand1, operand2, expected
):
    engine = create_calculator()

    result = engine.calculate(
        CalculationRequest(
            operation=operation, operand1=operand1, operand2=operand2
        )
    )

    assert result == CalculationResult(
        operation=operation,
        operand1=Decimal(str(operand1)),
        operand2=Decimal(str(operand2)),
        result=expected,
    )


def test_calculate_accepts_mapping_and_convenience_call_forms():
    engine = create_calculator()

    mapped = engine.calculate(
        {"operation": "add", "operand1": "0.1", "operand2": "0.2"}
    )
    direct = engine.calculate("subtract", 7, 2)

    assert mapped.result == Decimal("0.3")
    assert direct.result == Decimal("5")


def test_division_by_zero_is_rejected_and_not_recorded():
    engine = create_calculator()

    with pytest.raises(ZeroDivisionError, match="division by zero"):
        engine.calculate("divide", 1, 0)

    assert engine.get_history() == ()


@pytest.mark.parametrize(
    "request_data",
    [
        {"operation": "modulo", "operand1": 1, "operand2": 2},
        {"operation": "add", "operand1": "NaN", "operand2": 2},
        {"operation": "add", "operand1": 1, "operand2": "Infinity"},
        {"operation": "add", "operand1": 1, "operand2": 2, "extra": True},
    ],
)
def test_request_validation_rejects_unsupported_or_unsafe_input(request_data):
    with pytest.raises(ValidationError):
        create_calculator().calculate(request_data)


def test_history_preserves_order_and_is_an_immutable_snapshot():
    engine = create_calculator()
    first = engine.calculate("add", 1, 2)
    snapshot = engine.get_history()
    second = engine.calculate("multiply", 3, 4)

    assert snapshot == (first,)
    assert engine.history == (first, second)
    with pytest.raises(AttributeError):
        snapshot.append(second)


def test_clear_history_affects_only_the_current_engine():
    first_engine = create_calculator()
    second_engine = create_calculator()
    first_engine.calculate("add", 1, 1)
    second_engine.calculate("power", 3, 2)

    first_engine.clear_history()

    assert first_engine.history == ()
    assert [entry.result for entry in second_engine.history] == [Decimal("9")]


def test_history_limit_discards_only_the_oldest_successful_result():
    engine = create_calculator(history_limit=2)
    engine.calculate("add", 1, 1)
    second = engine.calculate("add", 2, 2)
    third = engine.calculate("add", 3, 3)

    assert engine.history == (second, third)


class ConstantStrategy(OperationStrategy):
    """Deterministic fake used to prove strategy injection."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Ignore operands and return a recognizable value."""

        return Decimal("42")


def test_factory_supports_injected_strategies_without_global_mutation():
    injected = dict(DEFAULT_STRATEGIES)
    injected[OperationType.ADD] = ConstantStrategy()

    custom_engine = create_calculator(injected)

    assert custom_engine.calculate("add", 100, 200).result == Decimal("42")
    assert create_calculator().calculate("add", 100, 200).result == Decimal("300")


def test_engine_rejects_incomplete_or_invalid_strategy_configuration():
    with pytest.raises(ValueError, match="missing strategies"):
        CalculatorEngine({OperationType.ADD: ConstantStrategy()})

    invalid = dict(DEFAULT_STRATEGIES)
    invalid[OperationType.ADD] = object()
    with pytest.raises(TypeError, match="OperationStrategy"):
        CalculatorEngine(invalid)


@pytest.mark.parametrize("history_limit", [0, -1])
def test_factory_rejects_non_positive_history_limit(history_limit):
    with pytest.raises(ValueError, match="greater than zero"):
        create_calculator(history_limit=history_limit)


@pytest.mark.parametrize("history_limit", [True, 1.5, "10"])
def test_factory_rejects_non_integer_history_limit(history_limit):
    with pytest.raises(TypeError, match="must be an integer"):
        create_calculator(history_limit=history_limit)


def test_invalid_call_shapes_are_rejected_before_dispatch():
    engine = create_calculator()

    with pytest.raises(TypeError, match="both operands"):
        engine.calculate("add", 1)
    with pytest.raises(TypeError, match="cannot accompany"):
        engine.calculate(
            {"operation": "add", "operand1": 1, "operand2": 2}, 1, 2
        )


class InfiniteStrategy(OperationStrategy):
    """Fake strategy that simulates an invalid operation result."""

    def execute(self, operand1: Decimal, operand2: Decimal) -> Decimal:
        """Return a non-finite value for output-validation coverage."""

        return Decimal("Infinity")


def test_non_finite_strategy_result_is_rejected_and_not_recorded():
    strategies = dict(DEFAULT_STRATEGIES)
    strategies[OperationType.ADD] = InfiniteStrategy()
    engine = create_calculator(strategies)

    with pytest.raises(ArithmeticError, match="finite result"):
        engine.calculate("add", 1, 2)

    assert engine.history == ()
