"""Acceptance and regression tests for the calculator engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from numbers import Real

import pytest
from pydantic import ValidationError

from Coding import CalculatorConfig, CalculatorEngine, OperationStrategy, create_calculator


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 3, 10),
        ("subtract", 7, 3, 4),
        ("multiply", 7, 3, 21),
        ("divide", 7, 2, 3.5),
        ("power", 2, 3, 8),
        (" ADD ", 1, 2, 3),
    ],
)
def test_standard_operations(operation, left, right, expected) -> None:
    assert create_calculator().calculate(operation, left, right) == expected


def test_large_integer_arithmetic_and_history_remain_exact() -> None:
    calculator = create_calculator()
    large_integer = 2**53

    assert calculator.calculate("add", large_integer, 1) == large_integer + 1
    assert calculator.calculate("subtract", large_integer + 1, large_integer) == 1

    addition, subtraction = calculator.get_history()
    assert (addition.left, addition.right, addition.result) == (large_integer, 1, large_integer + 1)
    assert (subtraction.left, subtraction.right, subtraction.result) == (
        large_integer + 1,
        large_integer,
        1,
    )
    assert all(isinstance(value, int) for value in (addition.left, addition.right, addition.result))


def test_history_is_bounded_immutable_ordered_and_clearable() -> None:
    calculator = create_calculator({"max_history": 2})
    calculator.calculate("add", 1, 1)
    calculator.calculate("multiply", 2, 3)
    calculator.calculate("subtract", 9, 1)

    history = calculator.get_history()
    assert isinstance(history, tuple)
    assert [(record.operation, record.result) for record in history] == [
        ("multiply", 6),
        ("subtract", 8),
    ]
    with pytest.raises(ValidationError):
        history[0].result = 99
    calculator.clear_history()
    assert calculator.get_history() == ()


@pytest.mark.parametrize(
    ("operation", "left", "right", "error"),
    [
        ("divide", 1, 0, ZeroDivisionError),
        ("modulo", 1, 2, ValueError),
        ("", 1, 2, ValueError),
        (1, 1, 2, TypeError),
        ("add", True, 2, TypeError),
        ("add", "1", 2, TypeError),
        ("add", float("inf"), 2, ValueError),
        ("power", -1, 0.5, TypeError),
    ],
)
def test_invalid_input_or_result_is_rejected_without_history(operation, left, right, error) -> None:
    calculator = create_calculator()
    with pytest.raises(error):
        calculator.calculate(operation, left, right)
    assert calculator.get_history() == ()


class RemainderStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left % right


class CustomReal:
    """Dependency-free virtual Real used to exercise generic finiteness checks."""

    def __init__(self, value: float) -> None:
        self.value = value

    def __float__(self) -> float:
        return self.value


Real.register(CustomReal)


class NonFiniteResultStrategy(OperationStrategy):
    def execute(self, left: Real, right: Real) -> Real:
        return CustomReal(float("inf"))


@pytest.mark.parametrize("operand_position", ["left", "right"])
def test_non_finite_custom_real_operand_is_rejected_without_history(operand_position: str) -> None:
    calculator = create_calculator()
    operands = {"left": 1, "right": 2}
    operands[operand_position] = CustomReal(float("inf"))

    with pytest.raises(ValueError, match=rf"{operand_position} must be finite"):
        calculator.calculate("add", operands["left"], operands["right"])
    assert calculator.get_history() == ()


def test_non_finite_custom_real_strategy_result_is_rejected_without_history() -> None:
    calculator = create_calculator(strategies={"non_finite": NonFiniteResultStrategy()})

    with pytest.raises(ValueError, match="result must be finite"):
        calculator.calculate("non_finite", 1, 2)
    assert calculator.get_history() == ()


def test_configuration_and_strategy_registry_are_validated() -> None:
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 0})
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 1, "unknown": True})
    with pytest.raises(ValueError):
        create_calculator(strategies={})
    with pytest.raises(TypeError):
        create_calculator(strategies={"bad": object()})
    with pytest.raises(ValueError, match="duplicate operation"):
        create_calculator(strategies={"custom": RemainderStrategy(), " CUSTOM ": RemainderStrategy()})


def test_direct_constructor_revalidates_constructed_configuration() -> None:
    invalid_config = CalculatorConfig.model_construct(max_history=0)
    with pytest.raises(ValidationError):
        CalculatorEngine(invalid_config, {"remainder": RemainderStrategy()})


def test_custom_strategy_dependency_is_injectable() -> None:
    calculator = create_calculator(strategies={"remainder": RemainderStrategy()})
    assert calculator.calculate("remainder", 7, 4) == 3
    with pytest.raises(ValueError, match="unsupported operation"):
        calculator.calculate("add", 1, 2)


def test_concurrent_calculations_preserve_every_history_record() -> None:
    calculator = create_calculator({"max_history": 50})
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: calculator.calculate("power", value, 2), range(50)))

    assert results == [value**2 for value in range(50)]
    assert len(calculator.get_history()) == 50
