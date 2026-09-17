"""Safe, Decimal-based modular expression calculator public API."""

from calculator import Calculator, CalculatorConfig
from exceptions import (
    ArithmeticDomainError,
    CalculatorError,
    ConfigurationError,
    DivisionByZeroError,
    EmptyExpressionError,
    EmptyParenthesesError,
    ExpressionEndingOperatorError,
    InvalidCharacterError,
    InvalidNumberError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    ParenthesisError,
    SizeLimitError,
    UnbalancedParenthesesError,
    UnsupportedOperatorError,
)
from history import CalculationHistory, HistoryEntry
from strategies import Associativity, OperationRegistry, OperationStrategy

__all__ = [
    "ArithmeticDomainError",
    "Associativity",
    "CalculationHistory",
    "Calculator",
    "CalculatorConfig",
    "CalculatorError",
    "ConfigurationError",
    "DivisionByZeroError",
    "EmptyExpressionError",
    "EmptyParenthesesError",
    "ExpressionEndingOperatorError",
    "HistoryEntry",
    "InvalidCharacterError",
    "InvalidNumberError",
    "InvalidOperatorSequenceError",
    "MissingOperandError",
    "MissingOperatorError",
    "OperationRegistry",
    "OperationStrategy",
    "ParenthesisError",
    "SizeLimitError",
    "UnbalancedParenthesesError",
    "UnsupportedOperatorError",
]
