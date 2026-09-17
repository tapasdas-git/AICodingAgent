"""Acceptance tests for expression evaluation and Decimal behavior."""

from decimal import Decimal

import pytest

from calculator import Calculator


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 + 3 + 4 + 5 + 6 + 7", Decimal("28")),
        ("2 + 3 * 4", Decimal("14")),
        ("2 + 3 * 4 - 8 / 2", Decimal("10")),
        ("100 / 5 * 2 + 3", Decimal("43")),
        ("10 - 2 - 3", Decimal("5")),
        ("100 / 10 / 2", Decimal("5")),
        ("2 ^ 3 ^ 2", Decimal("512")),
        ("(2 + 3) * 4", Decimal("20")),
        ("2 * (3 + 4)", Decimal("14")),
        ("((2 + 3) * (4 - 1))", Decimal("15")),
        ("0.1 + 0.2", Decimal("0.3")),
        ("-5 + 2", Decimal("-3")),
        ("2 * -3", Decimal("-6")),
        ("2 - -3", Decimal("5")),
        ("-(2 + 3)", Decimal("-5")),
    ],
)
def test_acceptance_expressions(expression: str, expected: Decimal) -> None:
    assert Calculator().calculate(expression) == expected


def test_all_supported_operators_can_share_one_expression() -> None:
    assert Calculator().calculate("2 ^ 3 + 12 / 3 * 2 - 1") == Decimal("15")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (".5 + .25", Decimal("0.75")),
        ("5. + 2.0", Decimal("7.0")),
        ("(-2) ^ 2", Decimal("4")),
        ("-2 ^ 2", Decimal("-4")),
        ("2 ^ -3", Decimal("0.125")),
        ("  1\t+\n2  ", Decimal("3")),
    ],
)
def test_decimal_unary_and_whitespace_edges(expression: str, expected: Decimal) -> None:
    assert Calculator().calculate(expression) == expected


def test_more_than_six_and_one_hundred_operands_are_supported() -> None:
    calculator = Calculator()
    assert calculator.calculate(" + ".join("1" for _ in range(7))) == Decimal("7")
    assert calculator.calculate(" + ".join("1" for _ in range(100))) == Decimal("100")
