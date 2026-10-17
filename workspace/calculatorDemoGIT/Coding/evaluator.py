"""Stack-based evaluator for validated reverse Polish notation."""

from __future__ import annotations

from decimal import Decimal, DecimalException, InvalidOperation

if __package__:
    from .exceptions import EvaluationError, InvalidDecimalError, MissingOperandError
    from .operations import OperationRegistry
    from .tokenizer import Token
else:
    from exceptions import EvaluationError, InvalidDecimalError, MissingOperandError
    from operations import OperationRegistry
    from tokenizer import Token


class Evaluator:
    """Evaluate RPN by dispatching every operation through its strategy."""

    def evaluate(self, tokens: tuple[Token, ...], registry: OperationRegistry) -> Decimal:
        """Return a Decimal result from an already validated RPN token stream."""
        values: list[Decimal] = []
        for token in tokens:
            if token.kind == "number":
                try:
                    values.append(Decimal(token.value))
                except InvalidOperation as exc:
                    raise InvalidDecimalError(f"Invalid decimal {token.value!r}.") from exc
                continue
            strategy = registry.get(token.value)
            if len(values) < strategy.arity:
                raise MissingOperandError(
                    f"Operator {token.value!r} does not have {strategy.arity} operands."
                )
            operands = values[-strategy.arity :]
            del values[-strategy.arity :]
            try:
                result = strategy.apply(*operands)
            except DecimalException as exc:
                raise EvaluationError(
                    f"Operator {token.value!r} could not evaluate its operands."
                ) from exc
            if not isinstance(result, Decimal) or not result.is_finite():
                raise EvaluationError(
                    f"Operator {token.value!r} must return a finite Decimal result."
                )
            values.append(result)
        if len(values) != 1:
            raise EvaluationError("Expression did not resolve to exactly one result.")
        return values[0]
