"""Stack evaluator for parsed calculator instructions."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from .exceptions import EvaluationError, MissingOperandError
from .parser import Instruction, UNARY_NEGATION
from .strategies import OperatorStrategy, apply_safely


class Evaluator:
    """Evaluate RPN instructions using registered operation strategies."""

    def __init__(self, strategies: Mapping[str, OperatorStrategy]) -> None:
        self._strategies = strategies

    def evaluate(self, instructions: tuple[Instruction, ...]) -> Decimal:
        """Evaluate a complete instruction stream without recursion."""
        stack: list[Decimal] = []
        for instruction in instructions:
            if isinstance(instruction.value, Decimal):
                stack.append(instruction.value)
            elif instruction.value == UNARY_NEGATION:
                if not stack:
                    raise MissingOperandError("Unary '-' is missing its operand.")
                stack.append(-stack.pop())
            else:
                if len(stack) < 2:
                    raise MissingOperandError(
                        f"Operator {instruction.value!r} is missing an operand."
                    )
                right = stack.pop()
                left = stack.pop()
                stack.append(
                    apply_safely(self._strategies[instruction.value], left, right)
                )
        if len(stack) != 1:
            raise EvaluationError("Expression did not produce exactly one result.")
        return stack[0]
