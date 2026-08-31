from __future__ import annotations

import pytest
from pydantic import ValidationError

from workspace.calculatorDemoO2.Coding.engine import CalculatorEngine, create_calculator_engine
from workspace.calculatorDemoO2.Coding.schemas import CalculationRequest, OperationType


@pytest.fixture
def calculator() -> CalculatorEngine:
    return create_calculator_engine()


@pytest.mark.parametrize(
    ("operation", "operand1", "operand2", "expected"),
    [
        (OperationType.ADD, 4, 3, 7),
        (OperationType.SUBTRACT, 4, 3, 1),
        (OperationType.MULTIPLY, 4, 3, 12),
        (OperationType.DIVIDE, 7, 2, 3.5),
        (OperationType.POWER, 2, 8, 256),
    ],
)
def test_standard_operations(calculator, operation, operand1, operand2, expected) -> None:
    result = calculator.calculate(
        CalculationRequest(operation=operation, operand1=operand1, operand2=operand2)
    )

    assert result.operation is operation
    assert result.operand1 == operand1
    assert result.operand2 == operand2
    assert result.result == expected


def test_division_by_zero_does_not_change_history(calculator: CalculatorEngine) -> None:
    request = CalculationRequest(operation="divide", operand1=8, operand2=0)

    with pytest.raises(ZeroDivisionError, match="division by zero"):
        calculator.calculate(request)

    assert calculator.get_history() == []


def test_history_is_ordered_and_returned_as_a_snapshot(calculator: CalculatorEngine) -> None:
    first = calculator.calculate(CalculationRequest(operation="add", operand1=2, operand2=5))
    second = calculator.calculate(CalculationRequest(operation="power", operand1=3, operand2=2))

    snapshot = calculator.get_history()
    assert snapshot == [first, second]
    snapshot.clear()
    assert calculator.get_history() == [first, second]

    calculator.clear_history()
    assert calculator.get_history() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "modulo", "operand1": 2, "operand2": 1},
        {"operation": "add", "operand1": float("inf"), "operand2": 1},
        {"operation": "add", "operand1": True, "operand2": 1},
        {"operation": "add", "operand1": "1", "operand2": 2},
        {"operation": "add", "operand1": 1},
        {"operation": "add", "operand1": 1, "operand2": 2, "unexpected": True},
    ],
)
def test_request_validation_rejects_invalid_input(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CalculationRequest.model_validate(payload)


def test_engine_rejects_unvalidated_request(calculator: CalculatorEngine) -> None:
    with pytest.raises(TypeError, match="CalculationRequest"):
        calculator.calculate({"operation": "add", "operand1": 1, "operand2": 2})  # type: ignore[arg-type]


def test_non_finite_result_is_rejected_without_history(calculator: CalculatorEngine) -> None:
    request = CalculationRequest(operation="multiply", operand1=1e308, operand2=1e308)

    with pytest.raises(ValueError, match="finite"):
        calculator.calculate(request)

    assert calculator.get_history() == []


def test_power_rejects_complex_results(calculator: CalculatorEngine) -> None:
    request = CalculationRequest(operation="power", operand1=-1, operand2=0.5)

    with pytest.raises(ValueError, match="real number"):
        calculator.calculate(request)


def test_factory_accepts_injected_operation_strategy() -> None:
    class ConstantStrategy:
        def execute(self, operand1: float, operand2: float) -> float:
            return 42

    calculator = create_calculator_engine(strategies={OperationType.ADD: ConstantStrategy()})

    result = calculator.calculate(CalculationRequest(operation="add", operand1=1, operand2=2))
    assert result.result == 42
    with pytest.raises(ValueError, match="not enabled"):
        calculator.calculate(CalculationRequest(operation="subtract", operand1=1, operand2=2))


def test_factory_validates_injected_strategies() -> None:
    with pytest.raises(ValueError, match="at least one"):
        create_calculator_engine(strategies={})
    with pytest.raises(TypeError, match="implement execute"):
        create_calculator_engine(strategies={OperationType.ADD: object()})  # type: ignore[dict-item]
