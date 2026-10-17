"""Single-pass tokenizer for Decimal arithmetic expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

if __package__:
    from .exceptions import InvalidCharacterError, InvalidDecimalError, UnsupportedOperatorError
else:
    from exceptions import InvalidCharacterError, InvalidDecimalError, UnsupportedOperatorError

TokenKind = Literal["number", "operator", "left_paren", "right_paren"]
_KNOWN_OPERATOR_CHARACTERS = frozenset("+-*/^%")


@dataclass(frozen=True, slots=True)
class Token:
    """An immutable lexical token with its source offset."""

    kind: TokenKind
    value: str
    position: int


class Tokenizer:
    """Tokenize expressions using the operator symbols supplied per request."""

    def tokenize(self, expression: str, operator_symbols: tuple[str, ...]) -> tuple[Token, ...]:
        """Return tokens or a precise domain error for malformed source text."""
        tokens: list[Token] = []
        position = 0
        while position < len(expression):
            character = expression[position]
            if character.isspace():
                position += 1
                continue
            if character.isdigit() or character == ".":
                start = position
                dot_count = 0
                while position < len(expression) and (
                    expression[position].isdigit() or expression[position] == "."
                ):
                    dot_count += expression[position] == "."
                    position += 1
                literal = expression[start:position]
                if dot_count > 1 or literal == ".":
                    raise InvalidDecimalError(
                        f"Invalid decimal {literal!r} at position {start}."
                    )
                tokens.append(Token("number", literal, start))
                continue
            if character in "()":
                kind: TokenKind = "left_paren" if character == "(" else "right_paren"
                tokens.append(Token(kind, character, position))
                position += 1
                continue
            symbol = next(
                (candidate for candidate in operator_symbols if expression.startswith(candidate, position)),
                None,
            )
            if symbol is not None:
                tokens.append(Token("operator", symbol, position))
                position += len(symbol)
                continue
            if character in _KNOWN_OPERATOR_CHARACTERS:
                raise UnsupportedOperatorError(
                    f"Unsupported operator {character!r} at position {position}."
                )
            raise InvalidCharacterError(
                f"Invalid character {character!r} at position {position}."
            )
        return tuple(tokens)
