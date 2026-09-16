"""Public facade and factory for the modular expression calculator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable

from .evaluator import Evaluator
from .exceptions import ConfigurationError
from .history import CalculationHistory, CalculationRecord
from .parser import Parser
from .strategies import OperatorStrategy, default_strategies
from .tokenizer import Token, Tokenizer


@dataclass(frozen=True, slots=True)
class CalculatorConfig:
    """Validated resource limits for calculator requests."""

    max_expression_length: int = 10_000
    max_tokens: int = 3_000
    max_operands: int = 1_000
    max_parenthesis_depth: int = 256

    def __post_init__(self) -> None:
        for name, value in (
            ("max_expression_length", self.max_expression_length),
            ("max_tokens", self.max_tokens),
            ("max_operands", self.max_operands),
            ("max_parenthesis_depth", self.max_parenthesis_depth),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"{name} must be a positive integer.")


class Calculator:
    """Parse and evaluate expressions while recording successful results."""

    def __init__(
        self,
        *,
        config: CalculatorConfig | None = None,
        strategies: Iterable[OperatorStrategy] | None = None,
        history: CalculationHistory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if config is not None and not isinstance(config, CalculatorConfig):
            raise ConfigurationError("config must be a CalculatorConfig instance.")
        if history is not None and not isinstance(history, CalculationHistory):
            raise ConfigurationError("history must be a CalculationHistory instance.")
        if clock is not None and not callable(clock):
            raise ConfigurationError("clock must be callable.")
        self._config = config if config is not None else CalculatorConfig()
        self._history = history if history is not None else CalculationHistory()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        try:
            selected = default_strategies() if strategies is None else tuple(strategies)
        except TypeError as exc:
            raise ConfigurationError("strategies must be an iterable.") from exc
        self._strategies: dict[str, OperatorStrategy] = {}
        for strategy in selected:
            self.register_operator(strategy)

    def register_operator(self, strategy: OperatorStrategy) -> None:
        """Register or replace an operation strategy by its symbol."""
        self._validate_strategy(strategy)
        self._strategies[strategy.symbol] = strategy

    def calculate(self, expression: str) -> Decimal:
        """Return an expression's Decimal result and record it on success."""
        tokenizer = Tokenizer(
            self._strategies,
            max_expression_length=self._config.max_expression_length,
            max_tokens=self._config.max_tokens,
        )
        tokens = tokenizer.tokenize(expression)
        parser = Parser(
            self._strategies,
            max_operands=self._config.max_operands,
            max_parenthesis_depth=self._config.max_parenthesis_depth,
        )
        instructions = parser.parse(tokens)
        result = Evaluator(self._strategies).evaluate(instructions)
        try:
            timestamp = self._clock()
        except Exception as exc:
            raise ConfigurationError("Clock failed to provide a timestamp.") from exc
        if not isinstance(timestamp, datetime):
            raise ConfigurationError("Clock must return a datetime instance.")
        # History is appended only after all validation and arithmetic succeeds.
        self._history.append(
            CalculationRecord(
                expression=expression,
                normalized_expression=self._normalize(tokens),
                result=result,
                timestamp=timestamp,
            )
        )
        return result

    def get_history(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable, ordered snapshot of successful calculations."""
        return self._history.retrieve()

    def clear_history(self) -> None:
        """Remove all records from this calculator's history."""
        self._history.clear()

    @staticmethod
    def _validate_strategy(strategy: OperatorStrategy) -> None:
        if not isinstance(strategy, OperatorStrategy):
            raise ConfigurationError("Strategies must implement OperatorStrategy.")
        if not strategy.symbol or any(
            character.isspace() or character.isalnum() or character in "()."
            for character in strategy.symbol
        ):
            raise ConfigurationError(
                "Operator symbols must contain only non-alphanumeric punctuation."
            )
        if isinstance(strategy.precedence, bool) or not isinstance(
            strategy.precedence, int
        ):
            raise ConfigurationError("Operator precedence must be an integer.")
        if strategy.associativity not in ("left", "right"):
            raise ConfigurationError(
                "Operator associativity must be 'left' or 'right'."
            )

    @staticmethod
    def _normalize(tokens: list[Token]) -> str:
        normalized = " ".join(token.text for token in tokens)
        return normalized.replace("( ", "(").replace(" )", ")")


def create_calculator(
    *,
    config: CalculatorConfig | None = None,
    strategies: Iterable[OperatorStrategy] | None = None,
    history: CalculationHistory | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Calculator:
    """Create a calculator with validated configuration and dependencies."""
    return Calculator(
        config=config,
        strategies=strategies,
        history=history,
        clock=clock,
    )
