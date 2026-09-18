"""Public facade for safe, extensible Decimal expression calculation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

if __package__:
    from .evaluator import Evaluator
    from .history import CalculationHistory, HistoryEntry
    from .operations import OperationRegistry, OperatorStrategy
    from .parser import Parser
    from .tokenizer import Token, Tokenizer
    from .validation import CalculatorConfig, ExpressionValidator
else:
    from evaluator import Evaluator
    from history import CalculationHistory, HistoryEntry
    from operations import OperationRegistry, OperatorStrategy
    from parser import Parser
    from tokenizer import Token, Tokenizer
    from validation import CalculatorConfig, ExpressionValidator


class Calculator:
    """Calculate validated expressions and retain only successful results."""

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
            raise TypeError("config must be a CalculatorConfig instance.")
        self._registry = registry if registry is not None else OperationRegistry.with_defaults()
        if not isinstance(self._registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry instance.")
        self._history = history if history is not None else CalculationHistory()
        if not isinstance(self._history, CalculationHistory):
            raise TypeError("history must be a CalculationHistory instance.")
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        if not callable(self._clock):
            raise TypeError("clock must be callable.")
        self._tokenizer = Tokenizer()
        self._parser = Parser()
        self._evaluator = Evaluator()
        self._validator = ExpressionValidator()

    def calculate(self, expression: str) -> Decimal:
        """Evaluate one expression and record it only after complete success."""
        source = self._validator.validate_source(expression, self._config)
        tokens = self._tokenizer.tokenize(source, self._registry.expression_symbols)
        self._validator.validate_tokens(tokens, self._config)
        rpn = self._parser.parse(tokens, self._registry)
        result = self._evaluator.evaluate(rpn, self._registry)
        timestamp = self._clock()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise TypeError("clock must return a timezone-aware datetime.")
        # History is the only side effect, so it occurs after all untrusted input,
        # custom strategy output, and injected clock output have been validated.
        self._history.append(
            HistoryEntry(source, self._normalize(tokens), result, timestamp)
        )
        return result

    def register_operator(self, strategy: OperatorStrategy, *, replace: bool = False) -> None:
        """Make a binary strategy available to future calculations."""
        self._registry.register(strategy, replace=replace)

    def get_history(self) -> tuple[HistoryEntry, ...]:
        """Return an immutable oldest-first snapshot of successful calculations."""
        return self._history.get_entries()

    def clear_history(self) -> None:
        """Remove all calculation history."""
        self._history.clear()

    @staticmethod
    def _normalize(tokens: tuple[Token, ...]) -> str:
        return " ".join(token.value for token in tokens)


def create_calculator(
    config: CalculatorConfig | None = None,
    *,
    registry: OperationRegistry | None = None,
    history: CalculationHistory | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Calculator:
    """Create a calculator with validated configuration and injectable dependencies."""
    return Calculator(config, registry=registry, history=history, clock=clock)
