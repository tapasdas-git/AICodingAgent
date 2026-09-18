"""Configuration and request-level resource validation."""

from __future__ import annotations

from dataclasses import dataclass

if __package__:
    from .exceptions import (
        ConfigurationError,
        EmptyExpressionError,
        SizeLimitError,
        UnbalancedParenthesesError,
    )
    from .tokenizer import Token
else:
    from exceptions import (
        ConfigurationError,
        EmptyExpressionError,
        SizeLimitError,
        UnbalancedParenthesesError,
    )
    from tokenizer import Token


@dataclass(frozen=True, slots=True)
class CalculatorConfig:
    """Bound expression resource use with validated positive limits."""

    max_expression_length: int = 100_000
    max_tokens: int = 50_000
    max_operands: int = 10_000
    max_parenthesis_depth: int = 1_000

    def __post_init__(self) -> None:
        """Reject booleans and non-positive resource limits."""
        for name, value in (
            ("max_expression_length", self.max_expression_length),
            ("max_tokens", self.max_tokens),
            ("max_operands", self.max_operands),
            ("max_parenthesis_depth", self.max_parenthesis_depth),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ConfigurationError(f"{name} must be a positive integer.")


class ExpressionValidator:
    """Validate public input type and configured size limits."""

    def validate_source(self, expression: object, config: CalculatorConfig) -> str:
        """Return a non-empty string that fits the source-length limit."""
        if not isinstance(expression, str):
            raise TypeError("Expression must be a string.")
        if not expression.strip():
            raise EmptyExpressionError("Expression must not be empty.")
        if len(expression) > config.max_expression_length:
            raise SizeLimitError(
                f"Expression length {len(expression)} exceeds limit {config.max_expression_length}."
            )
        return expression

    def validate_tokens(self, tokens: tuple[Token, ...], config: CalculatorConfig) -> None:
        """Reject token, operand, and nesting counts beyond configured limits."""
        if len(tokens) > config.max_tokens:
            raise SizeLimitError(f"Token count {len(tokens)} exceeds limit {config.max_tokens}.")
        operand_count = sum(token.kind == "number" for token in tokens)
        if operand_count > config.max_operands:
            raise SizeLimitError(
                f"Operand count {operand_count} exceeds limit {config.max_operands}."
            )
        opening_positions: list[int] = []
        for token in tokens:
            if token.kind == "left_paren":
                opening_positions.append(token.position)
                if len(opening_positions) > config.max_parenthesis_depth:
                    raise SizeLimitError(
                        f"Parenthesis depth {len(opening_positions)} exceeds limit "
                        f"{config.max_parenthesis_depth}."
                    )
            elif token.kind == "right_paren":
                if not opening_positions:
                    raise UnbalancedParenthesesError(
                        f"Unmatched ')' at position {token.position}."
                    )
                opening_positions.pop()
        if opening_positions:
            raise UnbalancedParenthesesError(
                f"Unmatched '(' at position {opening_positions[-1]}."
            )
