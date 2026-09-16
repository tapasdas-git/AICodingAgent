"""Acceptance and regression tests for the calculator facade."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from Coding import Calculator, CalculatorConfig, create_calculator
from Coding.exceptions import (
    ConfigurationError,
    DivisionByZeroError,
    EmptyExpressionError,
    EmptyParenthesesError,
    EvaluationError,
    ExpressionEndingWithOperatorError,
    InvalidCharacterError,
    InvalidDecimalError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
    UnsupportedOperatorError,
)
from Coding.strategies import OperatorStrategy


def test_documented_package_import_exposes_public_api() -> None:
    import Coding

    assert Coding.Calculator is Calculator
    assert Coding.create_calculator is create_calculator


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 + 3 + 4 + 5 + 6 + 7", "28"),
        ("2 + 3 * 4", "14"),
        ("2 + 3 * 4 - 8 / 2", "10"),
        ("100 / 5 * 2 + 3", "43"),
        ("10 - 2 - 3", "5"),
        ("100 / 10 / 2", "5"),
        ("2 ^ 3 ^ 2", "512"),
        ("-2 ^ 2", "-4"),
        ("(-2) ^ 2", "4"),
        ("2 ^ -3", "0.125"),
        ("-2 ^ -2", "-0.25"),
        ("-(2) ^ 2", "-4"),
        ("(2 + 3) * 4", "20"),
        ("2 * (3 + 4)", "14"),
        ("((1 + 2) * (3 + 2))", "15"),
        ("0.1 + 0.2", "0.3"),
        ("-5 + 2", "-3"),
        ("2 * -3", "-6"),
        ("-(2 + 3)", "-5"),
        (".5 + 1.25", "1.75"),
        ("2--3", "5"),
    ],
)
def test_supported_expressions(expression: str, expected: str) -> None:
    assert Calculator().calculate(expression) == Decimal(expected)


def test_one_hundred_operands_complete_without_recursion_failure() -> None:
    expression = "+".join("1" for _ in range(100))
    assert Calculator().calculate(expression) == Decimal("100")


@pytest.mark.parametrize(
    ("expression", "error", "message"),
    [
        ("", EmptyExpressionError, "empty"),
        ("   ", EmptyExpressionError, "empty"),
        ("2 + a", InvalidCharacterError, "'a'"),
        ("2 % 1", UnsupportedOperatorError, "%"),
        ("* 2", MissingOperandError, "Missing operand"),
        ("2 3", MissingOperatorError, "Missing operator"),
        ("2(3)", MissingOperatorError, "Missing operator"),
        ("2 + * 3", InvalidOperatorSequenceError, "sequence"),
        ("+2", InvalidOperatorSequenceError, "Unary '+'"),
        ("1..2 + 3", InvalidDecimalError, "1..2"),
        (". + 1", InvalidDecimalError, "'.'"),
        ("(1 + 2", UnbalancedParenthesesError, "Unmatched '('") ,
        ("1 + (", UnbalancedParenthesesError, "Unmatched '('") ,
        ("1 + 2)", UnbalancedParenthesesError, "Unmatched ')'"),
        ("()", EmptyParenthesesError, "Empty parentheses"),
        ("(   )", EmptyParenthesesError, "Empty parentheses"),
        ("1 +", ExpressionEndingWithOperatorError, "ends with operator"),
        ("2 / 0", DivisionByZeroError, "divide by zero"),
    ],
)
def test_domain_validation_errors(
    expression: str, error: type[Exception], message: str
) -> None:
    with pytest.raises(error) as captured:
        Calculator().calculate(expression)
    assert message in str(captured.value)


def test_non_string_expression_is_rejected_at_public_boundary() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        Calculator().calculate(123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("config", "expression", "message"),
    [
        (CalculatorConfig(max_expression_length=3), "1 + 2", "character limit"),
        (CalculatorConfig(max_tokens=2), "1 + 2", "token limit"),
        (CalculatorConfig(max_operands=2), "1 + 2 + 3", "operand limit"),
        (
            CalculatorConfig(max_parenthesis_depth=2),
            "(((1)))",
            "parenthesis-depth limit",
        ),
    ],
)
def test_configured_size_limits(
    config: CalculatorConfig, expression: str, message: str
) -> None:
    with pytest.raises(SizeLimitError, match=message):
        Calculator(config=config).calculate(expression)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_configuration_requires_positive_integer_limits(value: object) -> None:
    with pytest.raises(ConfigurationError, match="positive integer"):
        CalculatorConfig(max_operands=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    [
        ("config", "bad", "CalculatorConfig"),
        ("history", [], "CalculationHistory"),
        ("clock", 42, "callable"),
        ("strategies", 42, "iterable"),
    ],
)
def test_factory_dependencies_are_validated(
    keyword: str, value: object, message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        create_calculator(**{keyword: value})  # type: ignore[arg-type]


def test_history_records_successes_in_order_with_original_and_normalized_input() -> None:
    moments = iter(
        [
            datetime(2026, 9, 16, 10, tzinfo=timezone.utc),
            datetime(2026, 9, 16, 11, tzinfo=timezone.utc),
        ]
    )
    calculator = create_calculator(clock=lambda: next(moments))

    calculator.calculate(" 1+2 ")
    calculator.calculate(" 2*( 3+4 ) ")
    records = calculator.get_history()

    assert tuple(record.expression for record in records) == (
        " 1+2 ",
        " 2*( 3+4 ) ",
    )
    assert tuple(record.normalized_expression for record in records) == (
        "1 + 2",
        "2 * (3 + 4)",
    )
    assert tuple(record.result for record in records) == (Decimal("3"), Decimal("14"))
    assert records[0].timestamp == datetime(2026, 9, 16, 10, tzinfo=timezone.utc)


def test_history_snapshot_and_records_are_immutable_and_clearable() -> None:
    calculator = Calculator()
    calculator.calculate("1 + 1")
    snapshot = calculator.get_history()
    calculator.calculate("2 + 2")

    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 1
    with pytest.raises(FrozenInstanceError):
        snapshot[0].expression = "changed"  # type: ignore[misc]

    calculator.clear_history()
    assert calculator.get_history() == ()
    assert len(snapshot) == 1


def test_failed_calculations_are_not_recorded() -> None:
    calculator = Calculator()
    calculator.calculate("1 + 1")

    with pytest.raises(DivisionByZeroError):
        calculator.calculate("4 / 0")

    assert tuple(record.expression for record in calculator.get_history()) == ("1 + 1",)


class ModuloStrategy(OperatorStrategy):
    """Test-only strategy proving evaluator extensibility."""

    symbol = "%"
    precedence = 20

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Return the decimal remainder."""
        if right == 0:
            raise DivisionByZeroError("Cannot divide by zero.")
        return left % right


def test_custom_strategy_registers_without_evaluator_changes() -> None:
    calculator = Calculator()
    calculator.register_operator(ModuloStrategy())
    assert calculator.calculate("10 % 4 + 1") == Decimal("3")


class BrokenStrategy(OperatorStrategy):
    """Test-only invalid-result strategy."""

    symbol = "@"
    precedence = 20

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Deliberately violate the runtime result contract."""
        return "bad"  # type: ignore[return-value]


def test_strategy_results_are_validated_before_history_side_effect() -> None:
    calculator = Calculator()
    calculator.register_operator(BrokenStrategy())
    with pytest.raises(EvaluationError, match="non-Decimal"):
        calculator.calculate("2 @ 1")
    assert calculator.get_history() == ()


class ExplodingStrategy(OperatorStrategy):
    """Test-only strategy that leaks a non-domain implementation failure."""

    symbol = "!"
    precedence = 20

    def apply(self, left: Decimal, right: Decimal) -> Decimal:
        """Raise an implementation exception for boundary translation."""
        raise ValueError("internal strategy detail")


def test_strategy_exceptions_are_translated_to_safe_domain_errors() -> None:
    calculator = Calculator()
    calculator.register_operator(ExplodingStrategy())
    with pytest.raises(EvaluationError, match="failed while evaluating") as captured:
        calculator.calculate("2 ! 1")
    assert "internal strategy detail" not in str(captured.value)
    assert calculator.get_history() == ()


def test_invalid_strategy_registration_is_rejected() -> None:
    class InvalidAssociativity(OperatorStrategy):
        symbol = "&"
        precedence = 1
        associativity = "middle"  # type: ignore[assignment]

        def apply(self, left: Decimal, right: Decimal) -> Decimal:
            return left + right

    with pytest.raises(ConfigurationError, match="associativity"):
        Calculator().register_operator(InvalidAssociativity())


def test_clock_contract_is_validated_before_history_append() -> None:
    calculator = Calculator(clock=lambda: "today")  # type: ignore[arg-type,return-value]
    with pytest.raises(ConfigurationError, match="datetime"):
        calculator.calculate("1 + 1")
    assert calculator.get_history() == ()


def test_clock_failures_are_translated_before_history_append() -> None:
    def failing_clock() -> datetime:
        raise RuntimeError("internal clock detail")

    calculator = Calculator(clock=failing_clock)
    with pytest.raises(ConfigurationError, match="failed") as captured:
        calculator.calculate("1 + 1")
    assert "internal clock detail" not in str(captured.value)
    assert calculator.get_history() == ()
