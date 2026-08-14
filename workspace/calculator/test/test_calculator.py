from __future__ import annotations

import pytest

from workspace.calculator.Coding import Operation, create_calculator
from workspace.calculator.Coding.operations import OperationStrategy


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 3, 10),
        ("subtract", 7, 3, 4),
        ("multiply", 7, 3, 21),
        ("divide", 7, 2, 3.5),
        ("power", 2, 8, 256),
    ],
)
def test_standard_operations(operation: str, left: int, right: int, expected: int | float) -> None:
    assert create_calculator().calculate(operation, left, right) == expected


def test_arbitrary_precision_integer_operands_and_results_are_supported() -> None:
    calculator = create_calculator()
    huge_operand = 10**1000

    assert calculator.calculate("add", huge_operand, huge_operand) == 2 * huge_operand
    assert calculator.calculate("power", 10, 400) == 10**400
    assert [record.result for record in calculator.get_history()] == [2 * huge_operand, 10**400]


@pytest.mark.parametrize(
    ("operation", "left", "right", "message"),
    [
        ("unknown", 1, 2, "invalid calculation request"),
        ("add", True, 2, "operands must be finite numbers"),
        ("add", "1", 2, "operands must be finite numbers"),
        ("add", float("inf"), 2, "operands must be finite numbers"),
        ("add", float("nan"), 2, "operands must be finite numbers"),
        ("add", 1e308, 1e308, "finite real number"),
        ("power", -1, 0.5, "finite real number"),
        ("power", 10.0, 1000, "finite real number"),
    ],
)
def test_invalid_requests_are_rejected(
    operation: str, left: object, right: object, message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        create_calculator().calculate(operation, left, right)  # type: ignore[arg-type]


def test_division_by_zero_does_not_change_history() -> None:
    calculator = create_calculator()

    with pytest.raises(ZeroDivisionError, match="cannot divide by zero"):
        calculator.calculate("divide", 4, 0)

    assert calculator.get_history() == []


def test_history_tracks_successes_in_order_and_can_be_cleared() -> None:
    calculator = create_calculator()
    calculator.calculate("add", 2, 3)
    calculator.calculate(Operation.MULTIPLY, 4, 5)

    history = calculator.get_history()
    assert [record.model_dump(mode="json") for record in history] == [
        {"operation": "add", "left": 2, "right": 3, "result": 5},
        {"operation": "multiply", "left": 4, "right": 5, "result": 20},
    ]
    history.clear()
    assert len(calculator.get_history()) == 2

    calculator.clear_history()
    assert calculator.get_history() == []


class DoubleStrategy(OperationStrategy):
    def execute(self, left: int | float, right: int | float) -> int | float:
        return 2 * (left + right)


class OverflowStrategy(OperationStrategy):
    def execute(self, left: int | float, right: int | float) -> int | float:
        raise OverflowError("implementation detail")


def test_factory_accepts_injected_strategy() -> None:
    calculator = create_calculator({Operation.ADD: DoubleStrategy()})

    assert calculator.calculate("add", 2, 3) == 10
    with pytest.raises(ValueError, match="operation is not configured"):
        calculator.calculate("subtract", 2, 3)


def test_strategy_overflow_is_normalized_and_does_not_change_history() -> None:
    calculator = create_calculator({Operation.ADD: OverflowStrategy()})

    with pytest.raises(ValueError, match="operation must produce a finite real number"):
        calculator.calculate("add", 1, 2)

    assert calculator.get_history() == []


def test_factory_validates_strategy_configuration() -> None:
    with pytest.raises(ValueError, match="at least one"):
        create_calculator({})
    with pytest.raises(TypeError, match="OperationStrategy"):
        create_calculator({Operation.ADD: object()})  # type: ignore[dict-item]
