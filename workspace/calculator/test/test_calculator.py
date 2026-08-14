from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from Coding import Operation, OperationStrategy, create_calculator
from Coding.strategies import DEFAULT_STRATEGIES


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
def test_supported_operations(operation, left, right, expected):
    assert create_calculator().calculate(operation, left, right) == expected


def test_history_is_bounded_immutable_and_clearable():
    calculator = create_calculator(max_history=2)
    calculator.calculate("add", 1, 2)
    calculator.calculate("subtract", 5, 1)
    calculator.calculate("multiply", 3, 4)

    history = calculator.get_history()
    assert [item.result for item in history] == [4, 12]
    with pytest.raises(ValidationError):
        history[0].result = 99
    calculator.clear_history()
    assert calculator.get_history() == ()


@pytest.mark.parametrize("max_history", [0, -1, True, 1.5])
def test_invalid_capacity_is_rejected(max_history):
    with pytest.raises((ValueError, ValidationError)):
        create_calculator(max_history=max_history)


@pytest.mark.parametrize(
    ("operation", "left", "right", "error"),
    [
        ("modulo", 1, 2, ValidationError),
        ("add", "1", 2, ValidationError),
        ("add", float("inf"), 2, ValidationError),
        ("divide", 1, 0, ZeroDivisionError),
        ("power", -1, 0.5, ValueError),
        ("power", 1e308, 2, ValueError),
    ],
)
def test_invalid_calculations_do_not_change_history(operation, left, right, error):
    calculator = create_calculator()
    with pytest.raises(error):
        calculator.calculate(operation, left, right)
    assert calculator.get_history() == ()


class ConstantStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return 42


def test_factory_accepts_valid_injected_strategies():
    strategies = dict(DEFAULT_STRATEGIES)
    strategies[Operation.ADD] = ConstantStrategy()
    assert create_calculator(strategies=strategies).calculate("add", 1, 2) == 42


def test_factory_rejects_incomplete_or_invalid_strategies():
    with pytest.raises(ValueError):
        create_calculator(strategies={})
    invalid = dict(DEFAULT_STRATEGIES)
    invalid[Operation.ADD] = object()
    with pytest.raises(TypeError):
        create_calculator(strategies=invalid)


def test_concurrent_calculations_are_all_recorded():
    calculator = create_calculator(max_history=50)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: calculator.calculate("add", value, 1), range(50)))

    assert results == list(range(1, 51))
    assert len(calculator.get_history()) == 50
