from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from workspace.calculator.Coding import (
    CalculationError,
    CalculatorConfig,
    CalculatorEngine,
    DivisionByZeroError,
    InvalidStrategyError,
    OperationStrategy,
    UnknownOperationError,
    create_calculator_engine,
)


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 3, 10.0),
        ("subtract", 7, 3, 4.0),
        ("multiply", 7, 3, 21.0),
        ("divide", 7, 2, 3.5),
        ("power", 2, 4, 16.0),
    ],
)
def test_standard_operations(operation: str, left: float, right: float, expected: float) -> None:
    engine = create_calculator_engine()

    assert engine.calculate(operation, left, right) == expected
    assert engine.history[-1].operation == operation
    assert engine.history[-1].result == expected


def test_operation_name_is_normalized() -> None:
    engine = CalculatorEngine()

    assert engine.calculate("  ADD  ", 1, 2) == 3.0
    assert engine.history[0].operation == "add"


@pytest.mark.parametrize("operand", [True, False, "1", None, float("nan"), float("inf")])
def test_invalid_operands_are_rejected_without_history(operand: object) -> None:
    engine = CalculatorEngine()

    with pytest.raises(ValidationError):
        engine.calculate("add", operand, 2)

    assert engine.history == ()


def test_unknown_operation_and_division_by_zero_are_safe_and_not_recorded() -> None:
    engine = CalculatorEngine()

    with pytest.raises(UnknownOperationError, match="unknown operation"):
        engine.calculate("modulo", 5, 2)
    with pytest.raises(DivisionByZeroError, match="divide by zero"):
        engine.calculate("divide", 5, 0)

    assert engine.history == ()


@pytest.mark.parametrize(("left", "right"), [(1e308, 2), (-1, 0.5)])
def test_power_rejects_overflow_and_non_real_results(left: float, right: float) -> None:
    engine = CalculatorEngine()

    with pytest.raises(CalculationError):
        engine.calculate("power", left, right)

    assert engine.history == ()


def test_history_is_ordered_bounded_and_clearable() -> None:
    engine = create_calculator_engine(CalculatorConfig(history_limit=2))

    engine.calculate("add", 1, 1)
    engine.calculate("subtract", 5, 2)
    engine.calculate("multiply", 3, 4)

    assert [record.sequence for record in engine.history] == [2, 3]
    assert [record.result for record in engine.history] == [3.0, 12.0]

    engine.clear_history()
    assert engine.history == ()
    engine.calculate("add", 10, 5)
    assert engine.history[0].sequence == 4


def test_config_rejects_invalid_capacity_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        create_calculator_engine({"history_limit": 0})
    with pytest.raises(ValidationError):
        create_calculator_engine({"history_limit": 4, "unexpected": True})


class ModuloStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return "modulo"

    def execute(self, left: float, right: float) -> float:
        return left % right


class InvalidResultStrategy(OperationStrategy):
    @property
    def name(self) -> str:
        return "invalid_result"

    def execute(self, left: float, right: float) -> float:
        return "not a number"  # type: ignore[return-value]


def test_factory_accepts_injected_strategies() -> None:
    engine = create_calculator_engine(strategies=[ModuloStrategy()])

    assert engine.available_operations == ("modulo",)
    assert engine.calculate("modulo", 8, 3) == 2.0
    with pytest.raises(UnknownOperationError):
        engine.calculate("add", 1, 2)


def test_injected_strategy_result_is_validated_before_history_write() -> None:
    engine = create_calculator_engine(strategies=[InvalidResultStrategy()])

    with pytest.raises(CalculationError, match="operation 'invalid_result' failed"):
        engine.calculate("invalid_result", 1, 2)

    assert engine.history == ()


def test_engine_rejects_empty_duplicate_and_non_strategy_dependencies() -> None:
    with pytest.raises(InvalidStrategyError, match="at least one"):
        CalculatorEngine(strategies=[])
    with pytest.raises(InvalidStrategyError, match="duplicate"):
        CalculatorEngine(strategies=[ModuloStrategy(), ModuloStrategy()])
    with pytest.raises(InvalidStrategyError, match="OperationStrategy"):
        CalculatorEngine(strategies=[object()])  # type: ignore[list-item]


def test_concurrent_calculations_have_unique_ordered_history() -> None:
    engine = create_calculator_engine({"history_limit": 100})

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda value: engine.calculate("add", value, 1), range(100)))

    assert sorted(results) == [float(value) for value in range(1, 101)]
    assert [record.sequence for record in engine.history] == list(range(1, 101))
