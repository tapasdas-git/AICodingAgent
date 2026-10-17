"""Public API exports for the modular expression calculator."""

from .calculator import Calculator, create_calculator
from .exceptions import (
    CalculatorError,
    ConfigurationError,
    DivisionByZeroError,
    EmptyExpressionError,
    EmptyParenthesesError,
    EvaluationError,
    ExpressionEndsWithOperatorError,
    InvalidCharacterError,
    InvalidDecimalError,
    InvalidOperatorSequenceError,
    MissingOperandError,
    MissingOperatorError,
    SizeLimitError,
    UnbalancedParenthesesError,
    UnsupportedOperatorError,
)
from .history import CalculationHistory, HistoryEntry
from .operations import OperationRegistry, OperatorStrategy
from .validation import CalculatorConfig

__all__ = [
    "CalculationHistory",
    "Calculator",
    "CalculatorConfig",
    "CalculatorError",
    "ConfigurationError",
    "DivisionByZeroError",
    "EmptyExpressionError",
    "EmptyParenthesesError",
    "EvaluationError",
    "ExpressionEndsWithOperatorError",
    "HistoryEntry",
    "InvalidCharacterError",
    "InvalidDecimalError",
    "InvalidOperatorSequenceError",
    "MissingOperandError",
    "MissingOperatorError",
    "OperationRegistry",
    "OperatorStrategy",
    "SizeLimitError",
    "UnbalancedParenthesesError",
    "UnsupportedOperatorError",
    "create_calculator",
]
