"""In-memory, mutation-safe calculation history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from threading import RLock


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """Immutable record of one successful calculation."""

    expression: str
    normalized_expression: str
    result: Decimal
    timestamp: datetime


class CalculationHistory:
    """Store successful calculation records in insertion order."""

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self._lock = RLock()

    def record(self, entry: HistoryEntry) -> None:
        """Append one already validated calculation record."""
        if not isinstance(entry, HistoryEntry):
            raise TypeError("entry must be a HistoryEntry")
        with self._lock:
            self._entries.append(entry)

    def entries(self) -> tuple[HistoryEntry, ...]:
        """Return an immutable snapshot in oldest-to-newest order."""
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        """Remove all calculation records."""
        with self._lock:
            self._entries.clear()
