"""In-memory immutable calculation history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CalculationRecord:
    """Immutable details of one successful calculation."""

    expression: str
    normalized_expression: str
    result: Decimal
    timestamp: datetime


class CalculationHistory:
    """Store successful calculations in insertion order."""

    def __init__(self) -> None:
        self._records: list[CalculationRecord] = []

    def append(self, record: CalculationRecord) -> None:
        """Append a fully evaluated calculation record."""
        self._records.append(record)

    def retrieve(self) -> tuple[CalculationRecord, ...]:
        """Return an immutable snapshot that cannot mutate internal state."""
        return tuple(self._records)

    def clear(self) -> None:
        """Remove every stored calculation record."""
        self._records.clear()
