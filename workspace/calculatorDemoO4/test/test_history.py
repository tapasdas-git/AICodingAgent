"""Tests for ordered, isolated, successful calculation history."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from calculator import Calculator


def test_history_records_original_normalized_result_and_timestamp_in_order() -> None:
    instants = iter(
        (
            datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 17, 10, 1, tzinfo=timezone.utc),
        )
    )
    calculator = Calculator(clock=lambda: next(instants))

    calculator.calculate(" 1+2 ")
    calculator.calculate("3 * (4 + 1)")

    history = calculator.get_history()
    assert isinstance(history, tuple)
    assert [entry.expression for entry in history] == [" 1+2 ", "3 * (4 + 1)"]
    assert [entry.normalized_expression for entry in history] == [
        "1 + 2",
        "3 * ( 4 + 1 )",
    ]
    assert [entry.result for entry in history] == [Decimal("3"), Decimal("15")]
    assert [entry.timestamp for entry in history] == [
        datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 17, 10, 1, tzinfo=timezone.utc),
    ]


def test_history_snapshot_and_entries_do_not_expose_mutable_state() -> None:
    calculator = Calculator()
    calculator.calculate("2 + 2")
    snapshot = calculator.get_history()

    with pytest.raises(AttributeError):
        snapshot.append(snapshot[0])  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        snapshot[0].result = Decimal("99")  # type: ignore[misc]

    calculator.calculate("3 + 3")
    assert len(snapshot) == 1
    assert len(calculator.get_history()) == 2


def test_clear_history_removes_entries_without_affecting_old_snapshots() -> None:
    calculator = Calculator()
    calculator.calculate("5 - 2")
    snapshot = calculator.get_history()

    calculator.clear_history()

    assert snapshot[0].result == Decimal("3")
    assert calculator.get_history() == ()


def test_invalid_clock_result_fails_before_history_recording() -> None:
    calculator = Calculator(clock=lambda: "not a datetime")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="datetime"):
        calculator.calculate("1 + 1")
    assert calculator.get_history() == ()
