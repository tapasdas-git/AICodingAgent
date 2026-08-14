from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

REPOSITORY_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from workspace.calculator.Coding import Operation, create_calculator  # noqa: E402
from workspace.calculator.Coding.operations import AddStrategy  # noqa: E402


def test_public_package_api_can_be_imported_and_exercised():
    calculator = create_calculator()
    result = calculator.calculate(Operation.ADD, 2, 3)

    assert result.result == 5
    assert calculator.get_history() == (result,)


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 3, 10),
        ("subtract", 7, 3, 4),
        ("multiply", 7, 3, 21),
        ("divide", 7, 2, 3.5),
        ("power", 2, 4, 16),
    ],
)
def test_supported_operations(operation, left, right, expected):
    record = create_calculator().calculate(operation, left, right)
    assert record.result == expected
    assert record.operation == Operation(operation)


def test_history_tracks_successes_and_can_be_cleared():
    calculator = create_calculator()
    first = calculator.calculate("add", 1, 2)
    calculator.calculate("multiply", 3, 4)

    history = calculator.get_history()
    assert history[0] == first
    assert [item.result for item in history] == [3, 12]
    calculator.clear_history()
    assert calculator.get_history() == ()


@pytest.mark.parametrize(
    ("operation", "left", "right", "error"),
    [
        ("modulo", 1, 2, ValidationError),
        ("add", "1", 2, TypeError),
        ("add", True, 2, TypeError),
        ("add", float("inf"), 2, ValidationError),
        ("divide", 1, 0, ZeroDivisionError),
        ("power", -1, 0.5, ValueError),
        ("power", 10.0, 1000, ValueError),
    ],
)
def test_invalid_calculations_are_rejected_without_history(operation, left, right, error):
    calculator = create_calculator()
    with pytest.raises(error):
        calculator.calculate(operation, left, right)
    assert calculator.get_history() == ()


def test_factory_validates_injected_strategies():
    with pytest.raises(ValueError, match="every supported operation"):
        create_calculator({Operation.ADD: AddStrategy()})
    invalid = {operation: AddStrategy() for operation in Operation}
    invalid[Operation.ADD] = object()
    with pytest.raises(TypeError, match="OperationStrategy"):
        create_calculator(invalid)


def test_history_is_safe_during_concurrent_calculations():
    calculator = create_calculator()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: calculator.calculate("add", value, 1), range(100)))
    assert sorted(item.result for item in results) == list(range(1, 101))
    assert len(calculator.get_history()) == 100
