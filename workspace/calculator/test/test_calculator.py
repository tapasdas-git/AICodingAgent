from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from workspace.calculator.Coding import CalculatorConfig, CalculatorEngine, OperationStrategy, create_calculator


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 3, 10),
        ("subtract", 7, 3, 4),
        ("multiply", 7, 3, 21),
        ("divide", 7, 2, 3.5),
        ("power", 2, 5, 32),
    ],
)
def test_standard_operations(operation: str, left: float, right: float, expected: float) -> None:
    calculator = create_calculator()

    assert calculator.calculate(operation, left, right) == expected


@pytest.mark.parametrize(
    ("operation", "left", "right", "error"),
    [
        ("modulo", 1, 2, ValidationError),
        ("add", True, 2, ValidationError),
        ("add", "1", 2, ValidationError),
        ("add", math.inf, 2, ValidationError),
        ("divide", 1, 0, ZeroDivisionError),
        ("power", 10.0, 1000.0, ValueError),
        ("power", -1.0, 0.5, ValueError),
    ],
)
def test_invalid_calculations_are_rejected(
    operation: str,
    left: object,
    right: object,
    error: type[Exception],
) -> None:
    calculator = create_calculator()

    with pytest.raises(error):
        calculator.calculate(operation, left, right)  # type: ignore[arg-type]

    assert calculator.history == ()


def test_history_tracks_successes_in_order_and_is_bounded() -> None:
    calculator = create_calculator({"max_history": 2})

    calculator.calculate("add", 1, 2)
    calculator.calculate("multiply", 3, 4)
    snapshot = calculator.history
    calculator.calculate("subtract", 9, 4)

    assert [record.sequence for record in snapshot] == [1, 2]
    assert [record.sequence for record in calculator.history] == [2, 3]
    assert calculator.history[-1].result == 5

    calculator.clear_history()
    assert calculator.history == ()


def test_history_snapshot_and_records_are_immutable() -> None:
    calculator = create_calculator()
    calculator.calculate("add", 1, 2)

    snapshot = calculator.history

    with pytest.raises(ValidationError):
        snapshot[0].result = 99
    assert calculator.history[0].result == 3


def test_calculations_are_thread_safe_and_capacity_remains_bounded() -> None:
    calculation_count = 200
    calculator = create_calculator({"max_history": 75})

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda value: calculator.calculate("add", value, 1), range(calculation_count)))

    assert results == [value + 1 for value in range(calculation_count)]
    assert len(calculator.history) == 75
    assert [record.sequence for record in calculator.history] == list(range(126, 201))


@pytest.mark.parametrize("constructor", [CalculatorEngine, create_calculator])
def test_configuration_is_validated(constructor: object) -> None:
    with pytest.raises(ValidationError):
        constructor({"max_history": 0})  # type: ignore[operator]
    with pytest.raises(ValidationError):
        constructor({"unknown": 1})  # type: ignore[operator]


@pytest.mark.parametrize("constructor", [CalculatorEngine, create_calculator])
def test_forged_configuration_model_is_revalidated(constructor: object) -> None:
    forged_config = CalculatorConfig.model_construct(max_history=0)

    with pytest.raises(ValidationError):
        constructor(forged_config)  # type: ignore[operator]


class DoubleStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return 2 * (left + right)


def test_strategy_can_be_injected_without_removing_defaults() -> None:
    calculator = create_calculator(strategies={"add": DoubleStrategy()})

    assert calculator.calculate("add", 2, 3) == 10
    assert calculator.calculate("subtract", 5, 3) == 2


def test_direct_constructor_validates_strategies_and_provides_defaults() -> None:
    calculator = CalculatorEngine(strategies={"add": DoubleStrategy()})

    assert calculator.calculate("add", 2, 3) == 10
    assert calculator.calculate("multiply", 2, 3) == 6

    with pytest.raises(ValueError, match="unsupported strategy operation"):
        CalculatorEngine(strategies={"unknown": DoubleStrategy()})
    with pytest.raises(TypeError, match="OperationStrategy"):
        CalculatorEngine(strategies={"add": object()})  # type: ignore[dict-item]


def test_non_representable_integer_is_validation_error_without_history_change() -> None:
    calculator = create_calculator()
    calculator.calculate("add", 1, 2)
    history_before_failure = calculator.history

    with pytest.raises(ValidationError):
        calculator.calculate("add", 10**10000, 1)

    assert calculator.history == history_before_failure


def test_invalid_strategy_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported strategy operation"):
        create_calculator(strategies={"unknown": DoubleStrategy()})
    with pytest.raises(TypeError, match="OperationStrategy"):
        create_calculator(strategies={"add": object()})  # type: ignore[dict-item]
