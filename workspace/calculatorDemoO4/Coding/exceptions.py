"""Domain exceptions exposed by the expression calculator."""


class CalculatorError(ValueError):
    """Base class for safe, user-facing calculator failures."""


class ConfigurationError(CalculatorError):
    """Raised when calculator configuration or registration is invalid."""


class EmptyExpressionError(CalculatorError):
    """Raised when an expression is empty or contains only whitespace."""


class InvalidCharacterError(CalculatorError):
    """Raised when an expression contains an unrecognized character."""


class UnsupportedOperatorError(CalculatorError):
    """Raised when a recognizable but unregistered operator is used."""


class MissingOperandError(CalculatorError):
    """Raised when an operator or parenthesis lacks an operand."""


class MissingOperatorError(CalculatorError):
    """Raised when adjacent values or parentheses need an operator."""


class InvalidOperatorSequenceError(CalculatorError):
    """Raised when binary or unary operators occur in an invalid sequence."""


class InvalidNumberError(CalculatorError):
    """Raised when a numeric literal is not a valid decimal."""


class ParenthesisError(CalculatorError):
    """Base class for invalid parenthesis usage."""


class UnbalancedParenthesesError(ParenthesisError):
    """Raised when opening and closing parentheses do not balance."""


class EmptyParenthesesError(ParenthesisError):
    """Raised when a parenthesized expression contains no value."""


class DivisionByZeroError(CalculatorError, ZeroDivisionError):
    """Raised when division by zero is attempted."""


class ExpressionEndingOperatorError(CalculatorError):
    """Raised when an expression ends with an operator."""


class SizeLimitError(CalculatorError):
    """Raised when a configured expression resource limit is exceeded."""


class ArithmeticDomainError(CalculatorError):
    """Raised when valid syntax requests unsupported Decimal arithmetic."""
