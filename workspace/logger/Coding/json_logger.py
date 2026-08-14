"""Thread-safe, line-oriented JSON file logging with size-based rotation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any, Final


_LEVELS: Final[dict[str, int]] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
_RESERVED_FIELDS: Final[frozenset[str]] = frozenset({"timestamp", "level", "message"})


@dataclass(frozen=True, slots=True)
class LoggerConfig:
    """Validated configuration for :class:`JsonFileLogger`."""

    path: str | Path
    level: str = "INFO"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __post_init__(self) -> None:
        path = Path(self.path)
        level = _validate_level(self.level)
        if not isinstance(self.max_bytes, int) or isinstance(self.max_bytes, bool) or self.max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if not isinstance(self.backup_count, int) or isinstance(self.backup_count, bool) or self.backup_count < 0:
            raise ValueError("backup_count must be a non-negative integer")
        if not isinstance(self.timestamp_format, str) or not self.timestamp_format:
            raise ValueError("timestamp_format must be a non-empty string")
        if not path.name:
            raise ValueError("path must identify a file")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "level", level)


class JsonFileLogger:
    """Write complete JSON records atomically across threads."""

    def __init__(
        self,
        config: LoggerConfig,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(config, LoggerConfig):
            raise TypeError("config must be a LoggerConfig")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._config = config
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def log(self, level: str, message: str, /, **fields: Any) -> bool:
        """Write a record when ``level`` meets the configured threshold.

        Returns ``False`` when the record is filtered and ``True`` when written.
        """
        normalized_level = _validate_level(level)
        if not isinstance(message, str):
            raise TypeError("message must be a string")
        collisions = _RESERVED_FIELDS.intersection(fields)
        if collisions:
            raise ValueError(f"structured fields cannot replace reserved fields: {', '.join(sorted(collisions))}")
        if _LEVELS[normalized_level] < _LEVELS[self._config.level]:
            return False

        timestamp = self._clock()
        if not isinstance(timestamp, datetime):
            raise TypeError("clock must return a datetime")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc)
        record = {
            "timestamp": timestamp.strftime(self._config.timestamp_format),
            "level": normalized_level,
            "message": message,
            **fields,
        }
        try:
            payload = (
                json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TypeError("structured fields must be JSON serializable") from exc

        with self._lock:
            path = self._config.path
            path.parent.mkdir(parents=True, exist_ok=True)
            current_size = path.stat().st_size if path.exists() else 0
            if current_size and current_size + len(payload) > self._config.max_bytes:
                self._rotate()
            with path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
        return True

    def debug(self, message: str, **fields: Any) -> bool:
        """Log a DEBUG record."""
        return self.log("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> bool:
        """Log an INFO record."""
        return self.log("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> bool:
        """Log a WARNING record."""
        return self.log("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> bool:
        """Log an ERROR record."""
        return self.log("ERROR", message, **fields)

    def critical(self, message: str, **fields: Any) -> bool:
        """Log a CRITICAL record."""
        return self.log("CRITICAL", message, **fields)

    def _rotate(self) -> None:
        path = self._config.path
        if self._config.backup_count == 0:
            path.unlink(missing_ok=True)
            return
        oldest = Path(f"{path}.{self._config.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self._config.backup_count - 1, 0, -1):
            source = Path(f"{path}.{index}")
            if source.exists():
                source.replace(Path(f"{path}.{index + 1}"))
        if path.exists():
            path.replace(Path(f"{path}.1"))


def create_json_logger(
    path: str | Path,
    *,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ",
    clock: Callable[[], datetime] | None = None,
) -> JsonFileLogger:
    """Create a logger from validated configuration and injectable dependencies."""
    config = LoggerConfig(path, level, max_bytes, backup_count, timestamp_format)
    return JsonFileLogger(config, clock=clock)


def _validate_level(level: str) -> str:
    if not isinstance(level, str):
        raise TypeError("level must be a string")
    normalized = level.upper()
    if normalized not in _LEVELS:
        raise ValueError(f"unsupported log level: {level}")
    return normalized
