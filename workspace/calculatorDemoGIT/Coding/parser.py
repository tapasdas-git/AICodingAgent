"""Validation and linear-time infix-to-postfix expression parsing."""

from __future__ import annotations

if __package__:
    from .exceptions import (
        EmptyParenthesesError,
        ExpressionEndsWithOperatorError,
        InvalidOperatorSequenceError,
        MissingOperandError,
        MissingOperatorError,
        UnbalancedParenthesesError,
    )
    from .operations import OperationRegistry
    from .tokenizer import Token
else:
    from exceptions import (
        EmptyParenthesesError,
        ExpressionEndsWithOperatorError,
        InvalidOperatorSequenceError,
        MissingOperandError,
        MissingOperatorError,
        UnbalancedParenthesesError,
    )
    from operations import OperationRegistry
    from tokenizer import Token


class Parser:
    """Validate token grammar and produce reverse Polish notation."""

    def parse(self, tokens: tuple[Token, ...], registry: OperationRegistry) -> tuple[Token, ...]:
        """Convert infix tokens to RPN with configured precedence and associativity."""
        output: list[Token] = []
        operators: list[Token] = []
        expecting_operand = True
        previous: Token | None = None

        for token in tokens:
            if token.kind == "number":
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before {token.value!r} at position {token.position}."
                    )
                output.append(token)
                expecting_operand = False
            elif token.kind == "left_paren":
                if not expecting_operand:
                    raise MissingOperatorError(
                        f"Missing operator before '(' at position {token.position}."
                    )
                operators.append(token)
                expecting_operand = True
            elif token.kind == "right_paren":
                if previous is not None and previous.kind == "left_paren":
                    raise EmptyParenthesesError(
                        f"Empty parentheses at position {previous.position}."
                    )
                if expecting_operand:
                    if not any(item.kind == "left_paren" for item in operators):
                        raise UnbalancedParenthesesError(
                            f"Unmatched ')' at position {token.position}."
                        )
                    raise MissingOperandError(
                        f"Missing operand before ')' at position {token.position}."
                    )
                while operators and operators[-1].kind != "left_paren":
                    output.append(operators.pop())
                if not operators:
                    raise UnbalancedParenthesesError(
                        f"Unmatched ')' at position {token.position}."
                    )
                operators.pop()
                expecting_operand = False
            else:
                symbol = token.value
                if expecting_operand:
                    if symbol != "-":
                        if previous is None or previous.kind == "left_paren":
                            raise MissingOperandError(
                                f"Operator {symbol!r} at position {token.position} has no left operand."
                            )
                        raise InvalidOperatorSequenceError(
                            f"Invalid operator sequence {previous.value!r} {symbol!r} at position {token.position}."
                        )
                    token = Token("operator", "u-", token.position)
                self._push_operator(token, operators, output, registry)
                expecting_operand = True
            previous = token

        if expecting_operand:
            if previous is not None and previous.kind == "operator":
                raise ExpressionEndsWithOperatorError(
                    f"Expression ends with operator {previous.value!r} at position {previous.position}."
                )
            raise MissingOperandError("Expression is missing an operand.")

        while operators:
            token = operators.pop()
            if token.kind == "left_paren":
                raise UnbalancedParenthesesError(
                    f"Unmatched '(' at position {token.position}."
                )
            output.append(token)
        return tuple(output)

    @staticmethod
    def _push_operator(
        token: Token,
        stack: list[Token],
        output: list[Token],
        registry: OperationRegistry,
    ) -> None:
        # Equal-precedence right-associative operators remain stacked so exponent
        # chains and unary negatives bind from the right.
        incoming = registry.get(token.value)
        while stack and stack[-1].kind == "operator":
            top = registry.get(stack[-1].value)
            should_pop = top.precedence > incoming.precedence or (
                top.precedence == incoming.precedence and incoming.associativity == "left"
            )
            if not should_pop:
                break
            output.append(stack.pop())
        stack.append(token)
