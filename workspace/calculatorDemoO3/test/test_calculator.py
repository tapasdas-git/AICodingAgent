"""Behavioral tests for the modular calculator engine."""

import importlib

import pytest
from pydantic import ValidationError

from workspace.calculatorDemoO3.Coding.engine import (
    CalculatorEngine,
    OperationStrategy,
    create_calculator_engine,
)
from workspace.calculatorDemoO3.Coding.schemas import (
    CalculationRequest,
    CalculationResult,
    OperationType,
)


def make_request(
    operation: OperationType,
    operand1: float,
    operand2: float,
) -> CalculationRequest:
    """Build a strict request while keeping individual tests concise."""

    return CalculationRequest(
        operation=operation,
        operand1=operand1,
        operand2=operand2,
    )


def test_engine_supports_repository_root_package_import() -> None:
    module = importlib.import_module("workspace.calculatorDemoO3.Coding.engine")

    assert module.CalculatorEngine is CalculatorEngine


@pytest.mark.parametrize(
    ("operation", "operand1", "operand2", "expected"),
    [
        (OperationType.ADD, 7, 5, 12),
        (OperationType.SUBTRACT, 7, 5, 2),
        (OperationType.MULTIPLY, 7, 5, 35),
        (OperationType.DIVIDE, 9, 4, 2.25),
        (OperationType.POWER, 2, 5, 32),
    ],
)
def test_engine_executes_every_standard_operation(
    operation: OperationType,
    operand1: float,
    operand2: float,
    expected: float,
) -> None:
    calculation = create_calculator_engine().calculate(
        make_request(operation, operand1, operand2)
    )

    assert calculation == CalculationResult(
        operation=operation,
        operand1=float(operand1),
        operand2=float(operand2),
        result=expected,
    )


def test_division_by_zero_is_explicit_and_does_not_change_history() -> None:
    engine = CalculatorEngine()
    successful = engine.calculate(make_request(OperationType.ADD, 2, 3))

    with pytest.raises(ZeroDivisionError, match="cannot divide by zero"):
        engine.calculate(make_request(OperationType.DIVIDE, 9, 0))

    assert engine.get_history() == [successful]


def test_history_preserves_order_and_is_returned_as_a_snapshot() -> None:
    engine = CalculatorEngine()
    first = engine.calculate(make_request(OperationType.ADD, 1, 2))
    second = engine.calculate(make_request(OperationType.POWER, 3, 2))

    snapshot = engine.get_history()
    snapshot.clear()

    assert engine.get_history() == [first, second]


@pytest.mark.parametrize(
    "invalid_request",
    [
        {"operation": "modulo", "operand1": 1, "operand2": 2},
        {"operation": OperationType.ADD, "operand1": float("inf"), "operand2": 2},
        {"operation": OperationType.ADD, "operand1": 1, "operand2": float("nan")},
        {"operation": OperationType.ADD, "operand1": "1", "operand2": 2},
        {"operation": OperationType.ADD, "operand1": 1, "operand2": 2, "extra": 3},
    ],
)
def test_request_rejects_unknown_non_finite_coerced_or_extra_input(
    invalid_request: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CalculationRequest.model_validate(invalid_request)


def test_engine_requires_validated_request_boundary() -> None:
    with pytest.raises(TypeError, match="CalculationRequest"):
        CalculatorEngine().calculate(  # type: ignore[arg-type]
            {"operation": "add", "operand1": 1, "operand2": 2}
        )


def test_result_models_are_immutable() -> None:
    result = CalculatorEngine().calculate(make_request(OperationType.ADD, 1, 2))

    with pytest.raises(ValidationError):
        result.result = 99  # type: ignore[misc]


def test_injected_strategy_is_used_after_complete_configuration_validation() -> None:
    class ConstantStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return 42.0

    strategy = ConstantStrategy()
    strategies = {operation: strategy for operation in OperationType}
    engine = create_calculator_engine(strategies)

    assert isinstance(strategy, OperationStrategy)
    assert engine.calculate(make_request(OperationType.ADD, 1, 2)).result == 42

    with pytest.raises(ValueError, match="every supported operation"):
        create_calculator_engine({})

    string_keyed_strategies = {
        operation.value: strategy for operation in OperationType
    }
    with pytest.raises(ValueError, match="every supported operation"):
        create_calculator_engine(string_keyed_strategies)  # type: ignore[arg-type]


class _NonCallableStrategy:
    execute = 42


@pytest.mark.parametrize("invalid_strategy", [object(), _NonCallableStrategy()])
def test_engine_rejects_invalid_strategy_dependencies(invalid_strategy: object) -> None:
    class AddStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return operand1 + operand2

    strategies: dict[OperationType, object] = {
        operation: AddStrategy() for operation in OperationType
    }
    strategies[OperationType.ADD] = invalid_strategy

    with pytest.raises(TypeError, match="callable execute method"):
        create_calculator_engine(strategies)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_result",
    [float("inf"), float("nan"), "not-a-number"],
)
def test_invalid_strategy_result_is_rejected_without_history(
    invalid_result: object,
) -> None:
    class InvalidResultStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return invalid_result  # type: ignore[return-value]

    strategies = {operation: InvalidResultStrategy() for operation in OperationType}
    engine = CalculatorEngine(strategies)

    with pytest.raises(ArithmeticError, match="invalid or non-finite"):
        engine.calculate(make_request(OperationType.POWER, 2, 3))
    assert engine.get_history() == []


def test_strategy_exception_propagates_without_partial_history_update() -> None:
    class FailingStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            raise RuntimeError("strategy failed")

    strategies = {operation: FailingStrategy() for operation in OperationType}
    engine = CalculatorEngine(strategies)

    with pytest.raises(RuntimeError, match="strategy failed"):
        engine.calculate(make_request(OperationType.MULTIPLY, 2, 3))
    assert engine.get_history() == []
