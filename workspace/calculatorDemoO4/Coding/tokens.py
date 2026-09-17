"""Token value objects shared by calculator pipeline stages."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    """Lexical token categories recognized by the parser."""

    NUMBER = auto()
    OPERATOR = auto()
    LEFT_PARENTHESIS = auto()
    RIGHT_PARENTHESIS = auto()
    UNARY_NEGATION = auto()


@dataclass(frozen=True, slots=True)
class Token:
    """An immutable token containing its kind, source spelling, and offset."""

    kind: TokenKind
    lexeme: str
    position: int
