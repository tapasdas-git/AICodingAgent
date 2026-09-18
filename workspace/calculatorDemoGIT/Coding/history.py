"""Immutable successful-calculation history records and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from threading import RLock


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A successful calculation captured at an aware UTC timestamp."""

    original_expression: str
    normalized_expression: str
    result: Decimal
    timestamp: datetime


class CalculationHistory:
    """Store successful results in insertion order without leaking mutable state."""

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self._lock = RLock()

    def append(self, entry: HistoryEntry) -> None:
        """Append one fully evaluated history entry atomically."""
        with self._lock:
            self._entries.append(entry)

    def get_entries(self) -> tuple[HistoryEntry, ...]:
        """Return an immutable snapshot ordered from oldest to newest."""
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        """Remove every stored entry atomically."""
        with self._lock:
            self._entries.clear()
