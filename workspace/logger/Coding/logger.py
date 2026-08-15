"""A small, dependency-free JSON Lines file logger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping


_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_RESERVED_FIELDS = frozenset({"timestamp", "level", "message"})
Clock = Callable[[], datetime]
_PATH_LOCKS: dict[Path, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for_path(path: Path) -> threading.Lock:
    """Return the process-wide thread lock for a canonical log path."""
    canonical_path = path.resolve(strict=False)
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(canonical_path, threading.Lock())


@dataclass(frozen=True)
class LoggerConfig:
    """Validated configuration for :class:`JsonFileLogger`."""

    path: str | os.PathLike[str]
    level: str = "INFO"
    timestamp_format: str = "iso8601"
    max_bytes: int | None = None
    backup_count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.path, (str, os.PathLike)):
            raise TypeError("path must be a string or path-like object")
        if not os.fspath(self.path):
            raise ValueError("path must not be empty")
        path = Path(self.path)
        normalized_level = _normalize_level(self.level)
        object.__setattr__(self, "level", normalized_level)
        if not isinstance(self.timestamp_format, str) or not self.timestamp_format:
            raise ValueError("timestamp_format must be a non-empty string")
        if self.max_bytes is not None and (
            isinstance(self.max_bytes, bool) or not isinstance(self.max_bytes, int) or self.max_bytes <= 0
        ):
            raise ValueError("max_bytes must be a positive integer or None")
        if isinstance(self.backup_count, bool) or not isinstance(self.backup_count, int) or self.backup_count < 1:
            raise ValueError("backup_count must be a positive integer")


class JsonFileLogger:
    """Write one atomic JSON object per line, safe for threads sharing a path."""

    def __init__(self, config: LoggerConfig, *, clock: Clock) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._config = config
        self._path = Path(config.path)
        self._threshold = _LEVELS[config.level]
        self._clock = clock
        self._lock = _lock_for_path(self._path)

    def log(self, level: str, message: str, **fields: Any) -> bool:
        """Write a record and return ``True``, or ``False`` when filtered by level."""
        normalized_level = _normalize_level(level)
        if not isinstance(message, str):
            raise TypeError("message must be a string")
        if _LEVELS[normalized_level] < self._threshold:
            return False
        collisions = _RESERVED_FIELDS.intersection(fields)
        if collisions:
            raise ValueError(f"structured fields use reserved names: {', '.join(sorted(collisions))}")

        timestamp = self._clock()
        if not isinstance(timestamp, datetime):
            raise TypeError("clock must return a datetime")
        record = {
            "timestamp": self._format_timestamp(timestamp),
            "level": normalized_level,
            "message": message,
            **fields,
        }
        try:
            payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TypeError("log record must contain JSON-serializable values") from exc

        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed(len(payload))
            with self._path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
        return True

    def debug(self, message: str, **fields: Any) -> bool:
        return self.log("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> bool:
        return self.log("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> bool:
        return self.log("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> bool:
        return self.log("ERROR", message, **fields)

    def critical(self, message: str, **fields: Any) -> bool:
        return self.log("CRITICAL", message, **fields)

    def _format_timestamp(self, value: datetime) -> str:
        if self._config.timestamp_format == "iso8601":
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return value.strftime(self._config.timestamp_format)

    def _rotate_if_needed(self, incoming_size: int) -> None:
        max_bytes = self._config.max_bytes
        if max_bytes is None or not self._path.exists():
            return
        current_size = self._path.stat().st_size
        if current_size == 0 or current_size + incoming_size <= max_bytes:
            return
        oldest = Path(f"{self._path}.{self._config.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self._config.backup_count - 1, 0, -1):
            source = Path(f"{self._path}.{index}")
            if source.exists():
                os.replace(source, Path(f"{self._path}.{index + 1}"))
        os.replace(self._path, Path(f"{self._path}.1"))


def create_json_logger(
    path: str | os.PathLike[str],
    *,
    level: str = "INFO",
    timestamp_format: str = "iso8601",
    max_bytes: int | None = None,
    backup_count: int = 1,
    clock: Clock | None = None,
) -> JsonFileLogger:
    """Create a logger from validated configuration and injectable dependencies."""
    config = LoggerConfig(path, level, timestamp_format, max_bytes, backup_count)
    return JsonFileLogger(config, clock=clock or (lambda: datetime.now(timezone.utc)))


def _normalize_level(level: str) -> str:
    if not isinstance(level, str):
        raise TypeError("level must be a string")
    normalized = level.upper()
    if normalized not in _LEVELS:
        raise ValueError(f"unsupported log level: {level}")
    return normalized
