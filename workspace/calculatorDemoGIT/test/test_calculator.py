"""Behavior tests for arithmetic, precedence, and scaling acceptance criteria."""

from __future__ import annotations

from decimal import Decimal

import pytest

from calculator import Calculator, create_calculator


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
        ("(2 + 3) * 4", "20"),
        ("2 * (3 + 4)", "14"),
        ("((1 + 2) * (3 + 2))", "15"),
        ("0.1 + 0.2", "0.3"),
        ("-5 + 2", "-3"),
        ("2 * -3", "-6"),
        ("-(2 + 3)", "-5"),
    ],
)
def test_acceptance_expressions(expression: str, expected: str) -> None:
    assert Calculator().calculate(expression) == Decimal(expected)


def test_all_operators_can_appear_in_one_expression() -> None:
    assert Calculator().calculate("2 ^ 3 + 12 / 3 * 2 - 1") == Decimal("15")


def test_decimal_literals_support_leading_or_trailing_decimal_point() -> None:
    assert Calculator().calculate(".5 + 1.") == Decimal("1.5")


def test_repeated_unary_negation_and_exponent_binding() -> None:
    calculator = Calculator()
    assert calculator.calculate("--5") == Decimal("5")
    assert calculator.calculate("-2 ^ 2") == Decimal("-4")
    assert calculator.calculate("2 ^ -3") == Decimal("0.125")


def test_one_hundred_operands_evaluate_without_recursion_failure() -> None:
    expression = " + ".join("1" for _ in range(100))
    assert Calculator().calculate(expression) == Decimal("100")


def test_public_factory_constructs_independent_calculator() -> None:
    first = create_calculator()
    second = create_calculator()
    first.calculate("1 + 1")
    assert second.get_history() == ()


def test_package_exports_are_importable() -> None:
    from workspace.calculatorDemoGIT.Coding import Calculator as PackageCalculator

    assert PackageCalculator().calculate("6 * 7") == Decimal("42")
