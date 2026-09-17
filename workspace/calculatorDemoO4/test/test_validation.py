"""Tests for each public validation and arithmetic failure category."""

from decimal import Decimal, Overflow, localcontext

import pytest

from calculator import Calculator, CalculatorConfig
from exceptions import (
    ArithmeticDomainError,
    ConfigurationError,
    DivisionByZeroError,
    EmptyExpressionError,
    EmptyParenthesesError,
    ExpressionEndingOperatorError,
    InvalidCharacterError,
    InvalidNumberError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
    UnsupportedOperatorError,
)


@pytest.mark.parametrize("expression", ["", "   \t\n"])
def test_empty_input_is_rejected(expression: str) -> None:
    with pytest.raises(EmptyExpressionError, match="empty"):
        Calculator().calculate(expression)


def test_non_string_input_is_rejected_at_the_boundary() -> None:
    with pytest.raises(TypeError, match="string"):
        Calculator().calculate(123)  # type: ignore[arg-type]


@pytest.mark.parametrize("expression", ["1 $ 2", "one + 2"])
def test_invalid_characters_are_described(expression: str) -> None:
    with pytest.raises(InvalidCharacterError, match="position"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["5 % 2", "2 ** 3", "4 // 2"])
def test_recognizable_unregistered_operator_is_unsupported(expression: str) -> None:
    with pytest.raises(UnsupportedOperatorError, match="Unsupported"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["+ 1", "( * 2)"])
def test_missing_operand_is_rejected(expression: str) -> None:
    with pytest.raises(MissingOperandError, match="operand"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["1 2", "2 (3 + 4)", "(2) 3"])
def test_missing_operator_is_rejected(expression: str) -> None:
    with pytest.raises(MissingOperatorError, match="operator"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["1 + * 2", "1 / / 2", "--2"])
def test_invalid_operator_sequences_are_rejected(expression: str) -> None:
    with pytest.raises(InvalidOperatorSequenceError, match="sequence"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["1.2.3 + 1", ". + 1"])
def test_invalid_decimal_literals_are_rejected(expression: str) -> None:
    with pytest.raises(InvalidNumberError, match="decimal"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["² + 1", "1² + 1"])
def test_decimal_incompatible_unicode_digits_use_domain_error(expression: str) -> None:
    calculator = Calculator()

    with pytest.raises(InvalidNumberError, match="decimal"):
        calculator.calculate(expression)

    assert calculator.get_history() == ()


@pytest.mark.parametrize("expression", ["(1 + 2", "1 + 2)"])
def test_unbalanced_parentheses_are_rejected(expression: str) -> None:
    with pytest.raises(UnbalancedParenthesesError, match="[Uu]nmatched"):
        Calculator().calculate(expression)


@pytest.mark.parametrize("expression", ["()", "(   )"])
def test_empty_parentheses_are_rejected(expression: str) -> None:
    with pytest.raises(EmptyParenthesesError, match="Empty"):
        Calculator().calculate(expression)


def test_parenthesis_missing_an_operand_is_rejected() -> None:
    with pytest.raises(MissingOperandError, match="operand"):
        Calculator().calculate("(1 + )")


def test_division_by_zero_uses_domain_exception() -> None:
    with pytest.raises(DivisionByZeroError, match="zero"):
        Calculator().calculate("4 / (2 - 2)")


@pytest.mark.parametrize("expression", ["0 ^ -1", "(-0) ^ -2"])
def test_zero_to_negative_power_fails_without_recording_history(expression: str) -> None:
    calculator = Calculator()
    assert calculator.calculate("1 + 1") == Decimal("2")

    with pytest.raises(DivisionByZeroError, match="zero"):
        calculator.calculate(expression)

    assert [entry.expression for entry in calculator.get_history()] == ["1 + 1"]


def test_non_finite_exponent_result_fails_without_recording_history() -> None:
    calculator = Calculator()
    large_base = "9" * 101

    with localcontext() as context:
        context.traps[Overflow] = False
        with pytest.raises(ArithmeticDomainError, match="non-finite"):
            calculator.calculate(f"{large_base} ^ 10000")

    assert calculator.get_history() == ()


@pytest.mark.parametrize("expression", ["1 +", "2 *", "3 ^"])
def test_trailing_operator_uses_specific_exception(expression: str) -> None:
    with pytest.raises(ExpressionEndingOperatorError, match="ends"):
        Calculator().calculate(expression)


@pytest.mark.parametrize(
    ("config", "expression", "message"),
    [
        (CalculatorConfig(max_expression_length=3), "1 + 2", "length"),
        (CalculatorConfig(max_tokens=3), "1+2+3", "token count"),
        (CalculatorConfig(max_operands=2), "1+2+3", "Operand count"),
        (CalculatorConfig(max_parenthesis_depth=2), "(((1)))", "depth"),
        (CalculatorConfig(max_abs_exponent=3), "2 ^ 4", "Exponent"),
    ],
)
def test_each_configured_size_limit_is_enforced(
    config: CalculatorConfig, expression: str, message: str
) -> None:
    with pytest.raises(SizeLimitError, match=message):
        Calculator(config).calculate(expression)


@pytest.mark.parametrize("bad_value", [0, -1, True, 1.5])
def test_configuration_limits_must_be_positive_integers(bad_value: object) -> None:
    with pytest.raises(ConfigurationError, match="positive integer"):
        CalculatorConfig(max_operands=bad_value)  # type: ignore[arg-type]


def test_invalid_decimal_arithmetic_is_safely_wrapped() -> None:
    with pytest.raises(ArithmeticDomainError, match="Decimal arithmetic"):
        Calculator().calculate("(-2) ^ 0.5")


def test_failure_never_creates_history() -> None:
    calculator = Calculator()
    assert calculator.calculate("1 + 1") == Decimal("2")
    with pytest.raises(DivisionByZeroError):
        calculator.calculate("1 / 0")
    assert len(calculator.get_history()) == 1
