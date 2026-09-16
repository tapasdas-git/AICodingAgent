"""Iterative expression parser producing reverse Polish notation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from .exceptions import (
    EmptyParenthesesError,
    ExpressionEndingWithOperatorError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
)
from .strategies import OperatorStrategy
from .tokenizer import Token, TokenKind

UNARY_NEGATION = "__negate__"


@dataclass(frozen=True, slots=True)
class Instruction:
    """One RPN instruction containing a number or operator symbol."""

    value: Decimal | str


class Parser:
    """Parse tokens with an iterative shunting-yard algorithm."""

    # Unary negation binds below exponentiation but above multiplicative
    # operators, matching conventional arithmetic while still allowing 2^-3.
    _UNARY_PRECEDENCE = 25

    def __init__(
        self,
        strategies: Mapping[str, OperatorStrategy],
        *,
        max_operands: int,
        max_parenthesis_depth: int,
    ) -> None:
        self._strategies = strategies
        self._max_operands = max_operands
        self._max_parenthesis_depth = max_parenthesis_depth

    def parse(self, tokens: list[Token]) -> tuple[Instruction, ...]:
        """Validate tokens and convert them to evaluator-ready RPN."""
        output: list[Instruction] = []
        operators: list[Token | str] = []
        expecting_operand = True
        operand_count = 0
        depth = 0
        previous: Token | None = None

        for token in tokens:
            if token.kind is TokenKind.NUMBER:
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before number at position {token.position}."
                    )
                assert token.value is not None
                output.append(Instruction(token.value))
                operand_count += 1
                if operand_count > self._max_operands:
                    raise SizeLimitError(
                        f"Expression exceeds the {self._max_operands}-operand limit."
                    )
                expecting_operand = False
            elif token.kind is TokenKind.LEFT_PAREN:
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before '(' at position {token.position}."
                    )
                operators.append(token)
                depth += 1
                if depth > self._max_parenthesis_depth:
                    raise SizeLimitError(
                        "Expression exceeds the configured parenthesis-depth limit."
                    )
            elif token.kind is TokenKind.RIGHT_PAREN:
                if previous is not None and previous.kind is TokenKind.LEFT_PAREN:
                    raise EmptyParenthesesError(
                        f"Empty parentheses at position {previous.position}."
                    )
                if expecting_operand:
                    if not any(
                        isinstance(item, Token)
                        and item.kind is TokenKind.LEFT_PAREN
                        for item in operators
                    ):
                        raise UnbalancedParenthesesError(
                            f"Unmatched ')' at position {token.position}."
                        )
                    raise MissingOperandError(
                        f"Missing operand before ')' at position {token.position}."
                    )
                self._close_parenthesis(operators, output, token)
                depth -= 1
                expecting_operand = False
            else:
                expecting_operand = self._handle_operator(
                    token, expecting_operand, operators, output
                )
            previous = token

        if expecting_operand:
            unmatched_open = next(
                (
                    item
                    for item in reversed(operators)
                    if isinstance(item, Token)
                    and item.kind is TokenKind.LEFT_PAREN
                ),
                None,
            )
            if unmatched_open is not None:
                raise UnbalancedParenthesesError(
                    f"Unmatched '(' at position {unmatched_open.position}."
                )
            if previous is not None and previous.kind is TokenKind.OPERATOR:
                raise ExpressionEndingWithOperatorError(
                    f"Expression ends with operator {previous.text!r}."
                )
            raise MissingOperandError("Expression is missing an operand.")
        while operators:
            operator = operators.pop()
            if isinstance(operator, Token) and operator.kind is TokenKind.LEFT_PAREN:
                raise UnbalancedParenthesesError(
                    f"Unmatched '(' at position {operator.position}."
                )
            output.append(Instruction(self._operator_text(operator)))
        return tuple(output)

    def _handle_operator(
        self,
        token: Token,
        expecting_operand: bool,
        operators: list[Token | str],
        output: list[Instruction],
    ) -> bool:
        if expecting_operand:
            if token.text == "-":
                operators.append(UNARY_NEGATION)
                return True
            if token.text == "+":
                raise InvalidOperatorSequenceError(
                    f"Unary '+' is not supported at position {token.position}."
                )
            if not output and not operators:
                raise MissingOperandError(
                    f"Missing operand before {token.text!r} at position {token.position}."
                )
            raise InvalidOperatorSequenceError(
                f"Invalid operator sequence near {token.text!r} at position {token.position}."
            )

        current = self._strategies[token.text]
        while operators and self._should_pop(operators[-1], current):
            output.append(Instruction(self._operator_text(operators.pop())))
        operators.append(token)
        return True

    def _should_pop(
        self, stacked: Token | str, current: OperatorStrategy
    ) -> bool:
        if isinstance(stacked, Token) and stacked.kind is TokenKind.LEFT_PAREN:
            return False
        stacked_precedence = (
            self._UNARY_PRECEDENCE
            if stacked == UNARY_NEGATION
            else self._strategies[self._operator_text(stacked)].precedence
        )
        return stacked_precedence > current.precedence or (
            stacked_precedence == current.precedence
            and current.associativity == "left"
        )

    def _close_parenthesis(
        self,
        operators: list[Token | str],
        output: list[Instruction],
        closing: Token,
    ) -> None:
        while operators:
            operator = operators.pop()
            if isinstance(operator, Token) and operator.kind is TokenKind.LEFT_PAREN:
                return
            output.append(Instruction(self._operator_text(operator)))
        raise UnbalancedParenthesesError(
            f"Unmatched ')' at position {closing.position}."
        )

    @staticmethod
    def _operator_text(operator: Token | str) -> str:
        return operator if isinstance(operator, str) else operator.text
