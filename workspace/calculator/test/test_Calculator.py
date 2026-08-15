from concurrent.futures import ThreadPoolExecutor

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


def test_history_is_bounded_ordered_and_clearable():
    calculator = create_calculator({"max_history": 2})
    calculator.calculate("add", 1, 1)
    calculator.calculate("multiply", 2, 3)
    calculator.calculate("subtract", 9, 1)

    history = calculator.get_history()
    assert isinstance(history, tuple)
    assert [(item.operation, item.result) for item in history] == [
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
    ],
)
def test_invalid_input_is_rejected_without_history(operation, left, right, error):
    calculator = create_calculator()
    with pytest.raises(error):
        calculator.calculate(operation, left, right)
    assert calculator.get_history() == ()


def test_configuration_and_strategy_registry_are_validated():
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 0})
    with pytest.raises(ValidationError):
        create_calculator({"max_history": 1, "unknown": True})
    with pytest.raises(ValueError):
        create_calculator(strategies={})
    with pytest.raises(TypeError):
        create_calculator(strategies={"bad": object()})


@pytest.mark.parametrize(
    "config",
    [
        {"max_history": 0},
        {"max_history": 1, "unknown": True},
        CalculatorConfig.model_construct(max_history=0),
    ],
)
def test_direct_constructor_revalidates_all_configuration(config):
    with pytest.raises(ValidationError):
        CalculatorEngine(config, {"remainder": RemainderStrategy()})


def test_direct_constructor_accepts_and_normalizes_valid_mapping():
    calculator = CalculatorEngine({"max_history": 1}, {"remainder": RemainderStrategy()})
    assert calculator.calculate("remainder", 7, 4) == 3


class RemainderStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return left % right


def test_dependencies_are_injectable():
    calculator = create_calculator(strategies={"remainder": RemainderStrategy()})
    assert calculator.calculate("remainder", 7, 4) == 3
    with pytest.raises(ValueError, match="unsupported operation"):
        calculator.calculate("add", 1, 2)


def test_concurrent_calculations_preserve_every_record():
    calculator = create_calculator({"max_history": 50})
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: calculator.calculate("power", value, 2), range(50)))

    assert results == [value**2 for value in range(50)]
    assert len(calculator.get_history()) == 50
