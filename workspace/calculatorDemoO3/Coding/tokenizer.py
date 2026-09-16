"""Single-pass tokenizer for calculator expressions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum, auto
from typing import Collection

from .exceptions import (
    EmptyExpressionError,
    InvalidCharacterError,
    InvalidDecimalError,
    SizeLimitError,
    UnsupportedOperatorError,
)


class TokenKind(Enum):
    """Kinds of lexical tokens understood by the parser."""

    NUMBER = auto()
    OPERATOR = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()


@dataclass(frozen=True, slots=True)
class Token:
    """An immutable lexical token with its source position."""

    kind: TokenKind
    text: str
    position: int
    value: Decimal | None = None


class Tokenizer:
    """Convert validated expression text into tokens in linear time."""

    _OPERATOR_CHARACTERS = frozenset("+-*/^%")

    def __init__(
        self,
        operators: Collection[str],
        *,
        max_expression_length: int,
        max_tokens: int,
    ) -> None:
        self._operators = tuple(sorted(operators, key=len, reverse=True))
        self._max_expression_length = max_expression_length
        self._max_tokens = max_tokens

    def tokenize(self, expression: str) -> list[Token]:
        """Tokenize expression or raise a precise validation exception."""
        if not isinstance(expression, str):
            raise TypeError("Expression must be a string.")
        if not expression.strip():
            raise EmptyExpressionError("Expression cannot be empty.")
        if len(expression) > self._max_expression_length:
            raise SizeLimitError(
                f"Expression exceeds the {self._max_expression_length}-character limit."
            )

        tokens: list[Token] = []
        index = 0
        while index < len(expression):
            character = expression[index]
            if character.isspace():
                index += 1
                continue
            if character.isdigit() or character == ".":
                token, index = self._number(expression, index)
                tokens.append(token)
            elif character == "(":
                tokens.append(Token(TokenKind.LEFT_PAREN, character, index))
                index += 1
            elif character == ")":
                tokens.append(Token(TokenKind.RIGHT_PAREN, character, index))
                index += 1
            else:
                symbol = next(
                    (op for op in self._operators if expression.startswith(op, index)),
                    None,
                )
                if symbol is not None:
                    tokens.append(Token(TokenKind.OPERATOR, symbol, index))
                    index += len(symbol)
                elif character in self._OPERATOR_CHARACTERS:
                    raise UnsupportedOperatorError(
                        f"Unsupported operator {character!r} at position {index}."
                    )
                else:
                    raise InvalidCharacterError(
                        f"Invalid character {character!r} at position {index}."
                    )
            if len(tokens) > self._max_tokens:
                raise SizeLimitError(
                    f"Expression exceeds the {self._max_tokens}-token limit."
                )
        return tokens

    @staticmethod
    def _number(expression: str, start: int) -> tuple[Token, int]:
        index = start
        decimal_points = 0
        while index < len(expression) and (
            expression[index].isdigit() or expression[index] == "."
        ):
            if expression[index] == ".":
                decimal_points += 1
            index += 1
        text = expression[start:index]
        if decimal_points > 1 or not any(character.isdigit() for character in text):
            raise InvalidDecimalError(
                f"Invalid decimal literal {text!r} at position {start}."
            )
        try:
            value = Decimal(text)
        except InvalidOperation as exc:
            raise InvalidDecimalError(
                f"Invalid decimal literal {text!r} at position {start}."
            ) from exc
        return Token(TokenKind.NUMBER, text, start, value), index
