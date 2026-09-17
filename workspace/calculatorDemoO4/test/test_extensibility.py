"""Tests that operator behavior is supplied entirely by strategies."""

from decimal import Decimal

import pytest

from calculator import Calculator
from exceptions import ConfigurationError
from strategies import Associativity, OperationStrategy


class MaximumStrategy(OperationStrategy):
    """Test-only operator that selects the larger operand."""

    symbol = "@"
    precedence = 2
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the larger operand."""
        return max(left, right)


def test_custom_strategy_registers_without_evaluator_changes() -> None:
    calculator = Calculator()
    calculator.register_operator(MaximumStrategy())

    assert calculator.calculate("1 + 7 @ 3 * 2") == Decimal("15")


def test_duplicate_operator_requires_explicit_replacement() -> None:
    calculator = Calculator()
    calculator.register_operator(MaximumStrategy())
    with pytest.raises(ConfigurationError, match="already registered"):
        calculator.register_operator(MaximumStrategy())


class InvalidSymbolStrategy(OperationStrategy):
    """Test-only malformed strategy used to verify registration validation."""

    symbol = "word"
    precedence = 1
    associativity = Associativity.LEFT

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return an arbitrary value; registration must reject this class."""
        return left + right


def test_invalid_custom_symbol_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="punctuation"):
        Calculator().register_operator(InvalidSymbolStrategy())


class CountingAdditionStrategy(OperationStrategy):
    """Test strategy exposing the evaluator's amount of binary work."""

    symbol = "+"
    precedence = 1
    associativity = Associativity.LEFT

    def __init__(self) -> None:
        self.calls = 0

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Count and perform one addition."""
        self.calls += 1
        return left + right


def test_hundred_operand_evaluation_performs_linear_strategy_work() -> None:
    strategy = CountingAdditionStrategy()
    calculator = Calculator()
    calculator.register_operator(strategy, replace=True)

    assert calculator.calculate("+".join("1" for _ in range(100))) == Decimal("100")
    assert strategy.calls == 99
