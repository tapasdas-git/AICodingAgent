"""Postfix evaluator that dispatches through operation strategies."""

from decimal import Decimal, DecimalException

from exceptions import ArithmeticDomainError, MissingOperandError
from strategies import OperationRegistry
from tokens import Token, TokenKind


class Evaluator:
    """Evaluate validated postfix tokens using an injected registry."""

    def evaluate(self, postfix: tuple[Token, ...], registry: OperationRegistry) -> Decimal:
        """Evaluate postfix input in one pass and return its Decimal result."""
        stack: list[Decimal] = []
        for token in postfix:
            if token.kind is TokenKind.NUMBER:
                stack.append(Decimal(token.lexeme))
            elif token.kind is TokenKind.UNARY_NEGATION:
                if not stack:
                    raise MissingOperandError("Unary '-' is missing its operand")
                stack[-1] = -stack[-1]
            else:
                if len(stack) < 2:
                    raise MissingOperandError(
                        f"Operator {token.lexeme!r} is missing an operand"
                    )
                right = stack.pop()
                left = stack.pop()
                try:
                    stack.append(registry.get(token.lexeme).apply(left, right))
                except ArithmeticDomainError:
                    raise
                except DecimalException as exc:
                    raise ArithmeticDomainError(
                        f"Operator {token.lexeme!r} cannot evaluate {left} and {right}"
                    ) from exc
        if len(stack) != 1:
            raise MissingOperandError("Expression did not resolve to one result")
        return stack[0]
