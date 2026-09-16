"""Domain exceptions exposed by the expression calculator."""


class CalculatorError(Exception):
    """Base class for safe, user-facing calculator failures."""


class ConfigurationError(CalculatorError):
    """Raised when calculator configuration is internally inconsistent."""


class ExpressionValidationError(CalculatorError):
    """Base class for invalid expression input."""


class EmptyExpressionError(ExpressionValidationError):
    """Raised when an expression contains no non-whitespace content."""


class InvalidCharacterError(ExpressionValidationError):
    """Raised when an expression contains a non-arithmetic character."""


class UnsupportedOperatorError(ExpressionValidationError):
    """Raised when a recognizable arithmetic operator is not registered."""


class MissingOperandError(ExpressionValidationError):
    """Raised when an operator does not have its required operand."""


class MissingOperatorError(ExpressionValidationError):
    """Raised when adjacent values have no operator between them."""


class InvalidOperatorSequenceError(ExpressionValidationError):
    """Raised when binary operators occur in an invalid sequence."""


class InvalidDecimalError(ExpressionValidationError):
    """Raised when a numeric literal is not a valid decimal number."""


class UnbalancedParenthesesError(ExpressionValidationError):
    """Raised when opening and closing parentheses do not match."""


class EmptyParenthesesError(ExpressionValidationError):
    """Raised when a parenthesized group has no expression."""


class ExpressionEndingWithOperatorError(ExpressionValidationError):
    """Raised when an expression ends with a binary operator."""


class SizeLimitError(ExpressionValidationError):
    """Raised when a configured expression resource limit is exceeded."""


class EvaluationError(CalculatorError):
    """Raised when a valid expression cannot be evaluated arithmetically."""


class DivisionByZeroError(EvaluationError):
    """Raised when division by zero is attempted."""
