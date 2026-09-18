"""Domain exceptions exposed by the expression calculator."""


class CalculatorError(Exception):
    """Base class for safe, user-facing calculator failures."""


class ConfigurationError(CalculatorError):
    """Raised when calculator configuration or a strategy is invalid."""


class EmptyExpressionError(CalculatorError):
    """Raised when an expression is empty or contains only whitespace."""


class InvalidCharacterError(CalculatorError):
    """Raised when an expression contains a character outside the grammar."""


class UnsupportedOperatorError(CalculatorError):
    """Raised when a recognizable arithmetic operator is not registered."""


class MissingOperandError(CalculatorError):
    """Raised when an operator or closing parenthesis lacks an operand."""


class MissingOperatorError(CalculatorError):
    """Raised when adjacent values or parentheses lack an operator."""


class InvalidOperatorSequenceError(CalculatorError):
    """Raised when binary operators occur in an invalid sequence."""


class InvalidDecimalError(CalculatorError):
    """Raised when a numeric literal is not a valid decimal."""


class UnbalancedParenthesesError(CalculatorError):
    """Raised when opening and closing parentheses do not match."""


class EmptyParenthesesError(CalculatorError):
    """Raised when a parenthesized expression contains no value."""


class DivisionByZeroError(CalculatorError):
    """Raised when division is attempted with a zero divisor."""


class ExpressionEndsWithOperatorError(CalculatorError):
    """Raised when the final expression token is an operator."""


class SizeLimitError(CalculatorError):
    """Raised when a configured expression resource limit is exceeded."""


class EvaluationError(CalculatorError):
    """Raised when an operation cannot produce a valid Decimal result."""
