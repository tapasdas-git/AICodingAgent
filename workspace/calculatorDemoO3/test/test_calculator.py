"""Tests for the modular calculator engine."""

import importlib

import pytest
from pydantic import ValidationError

from workspace.calculatorDemoO3.Coding.engine import (
    CalculatorEngine,
    create_calculator_engine,
)
from workspace.calculatorDemoO3.Coding.schemas import CalculationRequest, OperationType


def request(operation: OperationType, operand1: float, operand2: float) -> CalculationRequest:
    return CalculationRequest(operation=operation, operand1=operand1, operand2=operand2)


def test_engine_supports_repository_style_package_import() -> None:
    module = importlib.import_module("workspace.calculatorDemoO3.Coding.engine")

    assert module.CalculatorEngine is CalculatorEngine


@pytest.mark.parametrize(
    ("operation", "operand1", "operand2", "expected"),
    [
        (OperationType.ADD, 7, 5, 12),
        (OperationType.SUBTRACT, 7, 5, 2),
        (OperationType.MULTIPLY, 7, 5, 35),
        (OperationType.POWER, 2, 5, 32),
    ],
)
def test_standard_operations(
    operation: OperationType,
    operand1: float,
    operand2: float,
    expected: float,
) -> None:
    engine = create_calculator_engine()

    calculation = engine.calculate(request(operation, operand1, operand2))

    assert calculation.result == expected
    assert calculation.operation is operation


def test_division_and_division_by_zero_handling() -> None:
    engine = CalculatorEngine()

    assert engine.calculate(request(OperationType.DIVIDE, 9, 4)).result == 2.25
    with pytest.raises(ZeroDivisionError, match="cannot divide by zero"):
        engine.calculate(request(OperationType.DIVIDE, 9, 0))
    assert len(engine.get_history()) == 1


def test_history_is_ordered_and_returned_as_a_snapshot() -> None:
    engine = CalculatorEngine()
    first = engine.calculate(request(OperationType.ADD, 1, 2))
    second = engine.calculate(request(OperationType.MULTIPLY, 3, 4))

    snapshot = engine.get_history()
    snapshot.clear()

    assert engine.get_history() == [first, second]


def test_request_rejects_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        CalculationRequest(operation="modulo", operand1=1, operand2=2)
    with pytest.raises(ValidationError):
        CalculationRequest(operation=OperationType.ADD, operand1=float("inf"), operand2=2)
    with pytest.raises(TypeError, match="CalculationRequest"):
        CalculatorEngine().calculate({"operation": "add", "operand1": 1, "operand2": 2})  # type: ignore[arg-type]


def test_injected_strategies_are_validated_and_used() -> None:
    class ConstantStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return 42.0

    strategies = {operation: ConstantStrategy() for operation in OperationType}
    engine = create_calculator_engine(strategies)

    assert engine.calculate(request(OperationType.ADD, 1, 2)).result == 42

    with pytest.raises(ValueError, match="every supported operation"):
        create_calculator_engine({})
    invalid_strategies = dict(strategies)
    invalid_strategies[OperationType.ADD] = object()  # type: ignore[assignment]
    with pytest.raises(TypeError, match="callable execute method"):
        create_calculator_engine(invalid_strategies)

    class NonCallableStrategy:
        execute = 42

    non_callable_strategies = dict(strategies)
    non_callable_strategies[OperationType.ADD] = NonCallableStrategy()  # type: ignore[assignment]
    with pytest.raises(TypeError, match="callable execute method"):
        create_calculator_engine(non_callable_strategies)


def test_non_finite_strategy_result_is_rejected_without_history() -> None:
    class InfiniteStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return float("inf")

    class AddStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return operand1 + operand2

    strategies = {operation: AddStrategy() for operation in OperationType}
    strategies[OperationType.POWER] = InfiniteStrategy()
    engine = CalculatorEngine(strategies)

    with pytest.raises(ArithmeticError, match="non-finite"):
        engine.calculate(request(OperationType.POWER, 2, 3))
    assert engine.get_history() == []
