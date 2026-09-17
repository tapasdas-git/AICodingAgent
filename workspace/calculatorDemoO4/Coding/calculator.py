"""Public calculator facade and validated runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from evaluator import Evaluator
from exceptions import ConfigurationError
from history import CalculationHistory, HistoryEntry
from parser import Parser
from strategies import OperationRegistry, OperationStrategy
from tokenizer import Tokenizer
from tokens import Token


@dataclass(frozen=True, slots=True)
class CalculatorConfig:
    """Resource limits used to validate calculator requests."""

    max_expression_length: int = 10_000
    max_tokens: int = 4_000
    max_operands: int = 1_000
    max_parenthesis_depth: int = 100
    max_abs_exponent: int = 10_000

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigurationError(f"{field_name} must be a positive integer")


class Calculator:
    """Validate, parse, evaluate, and record arithmetic expressions."""

    def __init__(
        self,
        config: CalculatorConfig | None = None,
        *,
        registry: OperationRegistry | None = None,
        history: CalculationHistory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config if config is not None else CalculatorConfig()
        if not isinstance(self._config, CalculatorConfig):
            raise TypeError("config must be a CalculatorConfig")
        self._registry = registry or OperationRegistry.with_defaults(
            self._config.max_abs_exponent
        )
        if not isinstance(self._registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry")
        self._history = history or CalculationHistory()
        if not isinstance(self._history, CalculationHistory):
            raise TypeError("history must be a CalculationHistory")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self._clock):
            raise TypeError("clock must be callable")
        self._tokenizer = Tokenizer(
            max_expression_length=self._config.max_expression_length,
            max_tokens=self._config.max_tokens,
        )
        self._parser = Parser(
            max_operands=self._config.max_operands,
            max_parenthesis_depth=self._config.max_parenthesis_depth,
        )
        self._evaluator = Evaluator()

    def calculate(self, expression: str) -> Decimal:
        """Return the result and record history only after complete success."""
        tokens = self._tokenizer.tokenize(expression, self._registry.symbols)
        postfix = self._parser.to_postfix(tokens, self._registry)
        result = self._evaluator.evaluate(postfix, self._registry)
        timestamp = self._clock()
        if not isinstance(timestamp, datetime):
            raise TypeError("clock must return a datetime")
        # Recording is deliberately last so every validation and arithmetic
        # failure leaves history unchanged.
        self._history.record(
            HistoryEntry(
                expression=expression,
                normalized_expression=self._normalize(tokens),
                result=result,
                timestamp=timestamp,
            )
        )
        return result

    def register_operator(
        self, strategy: OperationStrategy, *, replace: bool = False
    ) -> None:
        """Add an operator strategy without changing evaluator logic."""
        self._registry.register(strategy, replace=replace)

    def get_history(self) -> tuple[HistoryEntry, ...]:
        """Return an immutable snapshot of successful calculations."""
        return self._history.entries()

    def clear_history(self) -> None:
        """Remove every recorded calculation."""
        self._history.clear()

    @staticmethod
    def _normalize(tokens: tuple[Token, ...]) -> str:
        return " ".join(token.lexeme for token in tokens)
