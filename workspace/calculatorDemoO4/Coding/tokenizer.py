"""Linear tokenizer for validated arithmetic expressions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from exceptions import (
    EmptyExpressionError,
    InvalidCharacterError,
    InvalidNumberError,
    SizeLimitError,
    UnsupportedOperatorError,
)
from tokens import Token, TokenKind


_RECOGNIZABLE_UNSUPPORTED_OPERATORS = ("**", "//", "%", "&", "|", "=")


class Tokenizer:
    """Convert expression text into tokens without executing input."""

    def __init__(self, *, max_expression_length: int, max_tokens: int) -> None:
        self._max_expression_length = max_expression_length
        self._max_tokens = max_tokens

    def tokenize(self, expression: str, operator_symbols: tuple[str, ...]) -> tuple[Token, ...]:
        """Tokenize ``expression`` using the currently registered operators."""
        if not isinstance(expression, str):
            raise TypeError("expression must be a string")
        if not expression.strip():
            raise EmptyExpressionError("Expression must not be empty")
        if len(expression) > self._max_expression_length:
            raise SizeLimitError(
                f"Expression length {len(expression)} exceeds the configured limit "
                f"of {self._max_expression_length}"
            )

        tokens: list[Token] = []
        index = 0
        while index < len(expression):
            character = expression[index]
            if character.isspace():
                index += 1
                continue
            if character.isdigit() or character == ".":
                token, index = self._read_number(expression, index)
                tokens.append(token)
            elif character == "(":
                tokens.append(Token(TokenKind.LEFT_PARENTHESIS, character, index))
                index += 1
            elif character == ")":
                tokens.append(Token(TokenKind.RIGHT_PARENTHESIS, character, index))
                index += 1
            else:
                unsupported = next(
                    (
                        value
                        for value in _RECOGNIZABLE_UNSUPPORTED_OPERATORS
                        if expression.startswith(value, index)
                        and value not in operator_symbols
                    ),
                    None,
                )
                if unsupported is not None:
                    raise UnsupportedOperatorError(
                        f"Unsupported operator {unsupported!r} at position {index}"
                    )
                symbol = next(
                    (value for value in operator_symbols if expression.startswith(value, index)),
                    None,
                )
                if symbol is not None:
                    tokens.append(Token(TokenKind.OPERATOR, symbol, index))
                    index += len(symbol)
                else:
                    raise InvalidCharacterError(
                        f"Invalid character {character!r} at position {index}"
                    )
            if len(tokens) > self._max_tokens:
                raise SizeLimitError(
                    f"Expression token count exceeds the configured limit of {self._max_tokens}"
                )
        return tuple(tokens)

    @staticmethod
    def _read_number(expression: str, start: int) -> tuple[Token, int]:
        index = start
        decimal_points = 0
        digits = 0
        while index < len(expression):
            character = expression[index]
            if character.isdigit():
                digits += 1
                index += 1
            elif character == ".":
                decimal_points += 1
                index += 1
            else:
                break
        lexeme = expression[start:index]
        if decimal_points > 1 or digits == 0:
            raise InvalidNumberError(f"Invalid decimal literal {lexeme!r} at position {start}")
        try:
            Decimal(lexeme)
        except InvalidOperation as exc:
            raise InvalidNumberError(
                f"Invalid decimal literal {lexeme!r} at position {start}"
            ) from exc
        return Token(TokenKind.NUMBER, lexeme, start), index
