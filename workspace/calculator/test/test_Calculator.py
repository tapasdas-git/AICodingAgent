from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

import pytest
from pydantic import ValidationError

from workspace.calculator.Coding import (
    CalculatorConfig,
    CalculatorEngine,
    OperationStrategy,
    create_calculator,
)


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
def test_standard_operations(operation, left, right, expected):
    assert create_calculator().calculate(operation, left, right) == expected


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 2**53, 1, 2**53 + 1),
        ("subtract", -(2**53), 1, -(2**53) - 1),
        ("multiply", 2**53 + 1, 3, (2**53 + 1) * 3),
        ("power", 2, 100, 2**100),
    ],
)
def test_integer_arithmetic_and_history_remain_exact(operation, left, right, expected):
    calculator = create_calculator()

    result = calculator.calculate(operation, left, right)

    assert result == expected
    assert isinstance(result, int)
    record = calculator.get_history()[0]
    assert (record.left, record.right, record.result) == (left, right, expected)
    assert all(isinstance(value, int) for value in (record.left, record.right, record.result))


def test_float_arithmetic_remains_supported_without_changing_result_type():
    calculator = create_calculator()

    result = calculator.calculate("add", 1, 0.5)

    assert result == 1.5
    assert isinstance(result, float)
    assert calculator.get_history()[0].result == 1.5


def test_history_is_bounded_immutable_and_clearable():
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
        ("add", Fraction(1, 3), 2, TypeError),
        ("add", float("inf"), 2, ValueError),
        ("multiply", 1e308, 1e308, ValueError),
    ],
)
def test_invalid_input_or_result_is_rejected_without_history(operation, left, right, error):
    calculator = create_calculator()
    with pytest.raises(error):
        calculator.calculate(operation, left, right)
    assert calculator.get_history() == ()


class RemainderStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left % right


def test_configuration_and_strategy_registry_are_validated():
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 0})
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 1, "unknown": True})
    with pytest.raises(ValidationError):
        CalculatorEngine(
            CalculatorConfig.model_construct(max_history=0),
            {"remainder": RemainderStrategy()},
        )
    with pytest.raises(ValueError):
        create_calculator(strategies={})
    with pytest.raises(TypeError):
        create_calculator(strategies={"bad": object()})
    with pytest.raises(ValueError, match="duplicate operation"):
        create_calculator(strategies={"ADD": RemainderStrategy(), " add ": RemainderStrategy()})


@pytest.mark.parametrize("invalid_max_history", [True, False, "2", 2.0])
def test_max_history_rejects_coercive_non_integer_values(invalid_max_history):
    with pytest.raises(ValidationError):
        create_calculator({"max_history": invalid_max_history})


def test_dependencies_are_injectable_and_replace_defaults():
    calculator = create_calculator(strategies={"remainder": RemainderStrategy()})
    assert calculator.calculate("REMAINDER", 7, 4) == 3
    with pytest.raises(ValueError, match="unsupported operation"):
        calculator.calculate("add", 1, 2)


def test_concurrent_calculations_preserve_every_record():
    calculator = create_calculator({"max_history": 50})
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: calculator.calculate("power", value, 2), range(50)))

    assert results == [value**2 for value in range(50)]
    assert len(calculator.get_history()) == 50
