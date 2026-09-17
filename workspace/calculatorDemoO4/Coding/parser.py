"""Iterative shunting-yard parser for calculator tokens."""

from __future__ import annotations

from exceptions import (
    EmptyParenthesesError,
    ExpressionEndingOperatorError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
)
from strategies import Associativity, OperationRegistry
from tokens import Token, TokenKind


_UNARY_PRECEDENCE = 3


class Parser:
    """Validate token grammar and convert infix input to postfix form."""

    def __init__(self, *, max_operands: int, max_parenthesis_depth: int) -> None:
        self._max_operands = max_operands
        self._max_parenthesis_depth = max_parenthesis_depth

    def to_postfix(
        self, tokens: tuple[Token, ...], registry: OperationRegistry
    ) -> tuple[Token, ...]:
        """Return validated postfix tokens using registered precedence rules."""
        output: list[Token] = []
        operators: list[Token] = []
        expecting_operand = True
        previous: Token | None = None
        operand_count = 0
        parenthesis_depth = 0

        for token in tokens:
            if token.kind is TokenKind.NUMBER:
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before number at position {token.position}"
                    )
                output.append(token)
                operand_count += 1
                if operand_count > self._max_operands:
                    raise SizeLimitError(
                        f"Operand count exceeds the configured limit of {self._max_operands}"
                    )
                expecting_operand = False
            elif token.kind is TokenKind.LEFT_PARENTHESIS:
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before '(' at position {token.position}"
                    )
                parenthesis_depth += 1
                if parenthesis_depth > self._max_parenthesis_depth:
                    raise SizeLimitError(
                        "Parenthesis depth exceeds the configured limit of "
                        f"{self._max_parenthesis_depth}"
                    )
                operators.append(token)
            elif token.kind is TokenKind.RIGHT_PARENTHESIS:
                if parenthesis_depth == 0:
                    raise UnbalancedParenthesesError(
                        f"Unmatched ')' at position {token.position}"
                    )
                if expecting_operand:
                    if previous is not None and previous.kind is TokenKind.LEFT_PARENTHESIS:
                        raise EmptyParenthesesError(
                            f"Empty parentheses ending at position {token.position}"
                        )
                    raise MissingOperandError(
                        f"Missing operand before ')' at position {token.position}"
                    )
                while operators and operators[-1].kind is not TokenKind.LEFT_PARENTHESIS:
                    output.append(operators.pop())
                operators.pop()
                parenthesis_depth -= 1
                expecting_operand = False
            else:
                expecting_operand = self._handle_operator(
                    token, previous, expecting_operand, operators, output, registry
                )
            previous = token

        if parenthesis_depth:
            raise UnbalancedParenthesesError("Expression contains an unmatched '('")
        if expecting_operand:
            if previous is not None and previous.kind in {
                TokenKind.OPERATOR,
                TokenKind.UNARY_NEGATION,
            }:
                raise ExpressionEndingOperatorError(
                    f"Expression ends with operator {previous.lexeme!r}"
                )
            raise MissingOperandError("Expression is missing an operand")
        while operators:
            operator = operators.pop()
            if operator.kind is TokenKind.LEFT_PARENTHESIS:
                raise UnbalancedParenthesesError("Expression contains an unmatched '('")
            output.append(operator)
        return tuple(output)

    def _handle_operator(
        self,
        token: Token,
        previous: Token | None,
        expecting_operand: bool,
        operators: list[Token],
        output: list[Token],
        registry: OperationRegistry,
    ) -> bool:
        if expecting_operand:
            if token.lexeme == "-" and (
                previous is None
                or previous.kind in {TokenKind.OPERATOR, TokenKind.LEFT_PARENTHESIS}
            ):
                if (
                    previous is not None
                    and previous.kind is TokenKind.OPERATOR
                    and previous.lexeme == "-"
                    and operators
                    and operators[-1].kind is TokenKind.UNARY_NEGATION
                ):
                    raise InvalidOperatorSequenceError(
                        f"Invalid operator sequence near position {token.position}"
                    )
                operators.append(
                    Token(TokenKind.UNARY_NEGATION, token.lexeme, token.position)
                )
                return True
            if previous is None:
                raise MissingOperandError(
                    f"Missing left operand for {token.lexeme!r} at position {token.position}"
                )
            if previous.kind is TokenKind.LEFT_PARENTHESIS:
                raise MissingOperandError(
                    f"Missing operand before {token.lexeme!r} at position {token.position}"
                )
            raise InvalidOperatorSequenceError(
                f"Invalid operator sequence near position {token.position}"
            )

        incoming = registry.get(token.lexeme)
        while operators and operators[-1].kind in {
            TokenKind.OPERATOR,
            TokenKind.UNARY_NEGATION,
        }:
            top = operators[-1]
            top_precedence = (
                _UNARY_PRECEDENCE
                if top.kind is TokenKind.UNARY_NEGATION
                else registry.get(top.lexeme).precedence
            )
            should_pop = top_precedence > incoming.precedence or (
                top_precedence == incoming.precedence
                and incoming.associativity is Associativity.LEFT
            )
            if not should_pop:
                break
            output.append(operators.pop())
        operators.append(token)
        return True
