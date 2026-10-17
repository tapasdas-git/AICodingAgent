"""Tests for immutable history and open-ended strategy registration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from calculator import Calculator
from exceptions import DivisionByZeroError
from operations import OperatorStrategy


class MaximumStrategy(OperatorStrategy):
    """Test-only binary operator proving evaluator extensibility."""

    symbol, precedence, associativity = "@", 2, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        return max(operands)


def test_custom_operator_requires_no_evaluator_change() -> None:
    calculator = Calculator()
    calculator.register_operator(MaximumStrategy())
    assert calculator.calculate("2 + 9 @ 4 * 2") == Decimal("20")


def test_history_records_original_normalized_result_timestamp_and_order() -> None:
    timestamps = iter(
        [
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        ]
    )
    calculator = Calculator(clock=lambda: next(timestamps))
    calculator.calculate(" 1+2 ")
    calculator.calculate("4 * ( 3 - 1 )")

    entries = calculator.get_history()
    assert tuple(entry.original_expression for entry in entries) == (
        " 1+2 ",
        "4 * ( 3 - 1 )",
    )
    assert tuple(entry.normalized_expression for entry in entries) == (
        "1 + 2",
        "4 * ( 3 - 1 )",
    )
    assert tuple(entry.result for entry in entries) == (Decimal("3"), Decimal("8"))
    assert entries[0].timestamp == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert entries[1].timestamp == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_returned_history_cannot_mutate_internal_state() -> None:
    calculator = Calculator()
    calculator.calculate("1 + 2")
    snapshot = calculator.get_history()
    with pytest.raises(TypeError):
        snapshot[0] = snapshot[0]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        snapshot[0].original_expression = "changed"  # type: ignore[misc]
    assert calculator.get_history()[0].original_expression == "1 + 2"


def test_clear_history_does_not_mutate_existing_snapshot() -> None:
    calculator = Calculator()
    calculator.calculate("1 + 2")
    snapshot = calculator.get_history()
    calculator.clear_history()
    assert calculator.get_history() == ()
    assert snapshot[0].result == Decimal("3")


def test_failed_calculation_is_not_recorded() -> None:
    calculator = Calculator()
    calculator.calculate("1 + 1")
    with pytest.raises(DivisionByZeroError):
        calculator.calculate("1 / 0")
    assert tuple(entry.result for entry in calculator.get_history()) == (Decimal("2"),)


def test_clock_is_validated_before_history_side_effect() -> None:
    calculator = Calculator(clock=lambda: datetime(2026, 1, 1))
    with pytest.raises(TypeError, match="timezone-aware"):
        calculator.calculate("1 + 1")
    assert calculator.get_history() == ()
