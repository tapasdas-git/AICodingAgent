"""Tests for every public validation and safe failure category."""

from __future__ import annotations

from decimal import Decimal

import pytest

from calculator import Calculator
from exceptions import (
    ConfigurationError,
    DivisionByZeroError,
    EmptyExpressionError,
    EmptyParenthesesError,
    EvaluationError,
    ExpressionEndsWithOperatorError,
    InvalidCharacterError,
    InvalidDecimalError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
    UnsupportedOperatorError,
)
from operations import OperationRegistry, OperatorStrategy
from validation import CalculatorConfig


@pytest.mark.parametrize("expression", ["", "  \t\n"])
def test_empty_input(expression: str) -> None:
    with pytest.raises(EmptyExpressionError, match="must not be empty"):
        Calculator().calculate(expression)


def test_non_string_input_is_rejected_at_public_boundary() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        Calculator().calculate(123)  # type: ignore[arg-type]


def test_invalid_character_identifies_character_and_position() -> None:
    with pytest.raises(InvalidCharacterError, match=r"'a'.*position 4"):
        Calculator().calculate("2 + a")


def test_unsupported_operator_is_distinct_from_invalid_character() -> None:
    with pytest.raises(UnsupportedOperatorError, match=r"'%'.*position 2"):
        Calculator().calculate("2 % 1")


@pytest.mark.parametrize("expression", ["+ 2", "* 2", "( / 2)"])
def test_missing_left_operand(expression: str) -> None:
    with pytest.raises(MissingOperandError, match="no left operand"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["2 3", "2(3)", "(2)3", "(2)(3)"])
def test_missing_operator(expression: str) -> None:
    with pytest.raises(MissingOperatorError, match="Missing operator"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["2 + * 3", "2 / ^ 3", "2 - / 3"])
def test_invalid_binary_operator_sequence(expression: str) -> None:
    with pytest.raises(InvalidOperatorSequenceError, match="Invalid operator sequence"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["1..2 + 3", ". + 1", "2.3.4"])
def test_invalid_decimal(expression: str) -> None:
    with pytest.raises(InvalidDecimalError, match="Invalid decimal"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["()", "(  )", "2 + ()"])
def test_empty_parentheses(expression: str) -> None:
    with pytest.raises(EmptyParenthesesError, match="Empty parentheses"):
        Calculator().calculate(expression)


@pytest.mark.parametrize(
    "expression", ["(2 + 3", "2 + 3)", ")2(", "2 + (", "(2 +"]
)
def test_unbalanced_parentheses(expression: str) -> None:
    with pytest.raises(UnbalancedParenthesesError, match="Unmatched"):
        Calculator().calculate(expression)


def test_missing_operand_before_closing_parenthesis() -> None:
    with pytest.raises(MissingOperandError, match="Missing operand before"):
        Calculator().calculate("(2 + )")


@pytest.mark.parametrize("expression", ["2 +", "2 *", "2 ^ -"])
def test_expression_ending_with_operator(expression: str) -> None:
    with pytest.raises(ExpressionEndsWithOperatorError, match="ends with operator"):
        Calculator().calculate(expression)


def test_division_by_zero_uses_domain_exception() -> None:
    with pytest.raises(DivisionByZeroError, match="divide by zero"):
        Calculator().calculate("3 / (2 - 2)")


@pytest.mark.parametrize(
    ("config", "expression", "message"),
    [
        (CalculatorConfig(max_expression_length=3), "1 + 1", "Expression length"),
        (CalculatorConfig(max_tokens=2), "1 + 1", "Token count"),
        (CalculatorConfig(max_operands=2), "1 + 2 + 3", "Operand count"),
        (CalculatorConfig(max_parenthesis_depth=2), "(((1)))", "Parenthesis depth"),
    ],
)
def test_configured_size_limits(
    config: CalculatorConfig, expression: str, message: str
) -> None:
    with pytest.raises(SizeLimitError, match=message):
        Calculator(config).calculate(expression)


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "10"])
def test_configuration_requires_positive_integer_limits(value: object) -> None:
    with pytest.raises(ConfigurationError, match="positive integer"):
        CalculatorConfig(max_operands=value)  # type: ignore[arg-type]


def test_invalid_dependency_types_are_rejected() -> None:
    with pytest.raises(TypeError, match="CalculatorConfig"):
        Calculator(config=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="OperationRegistry"):
        Calculator(registry=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="callable"):
        Calculator(clock=object())  # type: ignore[arg-type]


class InfiniteStrategy(OperatorStrategy):
    """Deliberately violate the finite Decimal strategy result contract."""

    symbol, precedence, associativity = "@", 2, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        return Decimal("Infinity")


def test_invalid_custom_strategy_result_is_a_safe_domain_error() -> None:
    calculator = Calculator()
    calculator.register_operator(InfiniteStrategy())
    with pytest.raises(EvaluationError, match="finite Decimal"):
        calculator.calculate("1 @ 2")
    assert calculator.get_history() == ()


def test_registry_rejects_duplicate_default_operator() -> None:
    registry = OperationRegistry.with_defaults()
    with pytest.raises(ConfigurationError, match="already registered"):
        registry.register(registry.get("+"))
