"""Thread-safe, newline-delimited JSON file logger with size rotation."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_RESERVED_FIELDS = frozenset({"timestamp", "level", "message"})


@dataclass(frozen=True, slots=True)
class LoggerConfig:
    """Validated configuration for :class:`JSONFileLogger`."""

    path: str | Path
    level: str = "INFO"
    max_bytes: int = 0
    backup_count: int = 0
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        path = Path(self.path)
        if not path.name:
            raise ValueError("path must identify a log file")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "level", _validate_level(self.level))
        if isinstance(self.max_bytes, bool) or not isinstance(self.max_bytes, int):
            raise TypeError("max_bytes must be an integer")
        if self.max_bytes < 0:
            raise ValueError("max_bytes cannot be negative")
        if isinstance(self.backup_count, bool) or not isinstance(self.backup_count, int):
            raise TypeError("backup_count must be an integer")
        if self.backup_count < 0:
            raise ValueError("backup_count cannot be negative")
        if not isinstance(self.encoding, str) or not self.encoding:
            raise ValueError("encoding must be a non-empty string")


class JSONFileLogger:
    """Write complete JSON records atomically within a logger instance."""

    def __init__(
        self,
        config: LoggerConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        opener: Callable[..., TextIO] = open,
    ) -> None:
        if not isinstance(config, LoggerConfig):
            raise TypeError("config must be a LoggerConfig")
        self._config = config
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._opener = opener
        self._lock = threading.RLock()
        self._closed = False
        config.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self._open_stream()

    @property
    def path(self) -> Path:
        return self._config.path

    def log(self, level: str, message: str, **fields: Any) -> bool:
        """Write a record and return whether it passed the configured threshold."""
        normalized_level = _validate_level(level)
        if not isinstance(message, str):
            raise TypeError("message must be a string")
        collisions = _RESERVED_FIELDS.intersection(fields)
        if collisions:
            raise ValueError(f"fields cannot replace reserved keys: {', '.join(sorted(collisions))}")
        if _LEVELS[normalized_level] < _LEVELS[self._config.level]:
            return False

        timestamp = self._clock()
        if not isinstance(timestamp, datetime):
            raise TypeError("clock must return a datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        record = {
            "timestamp": timestamp.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": normalized_level,
            "message": message,
            **fields,
        }
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        except (TypeError, ValueError) as exc:
            raise TypeError("all log fields must be JSON serializable") from exc

        with self._lock:
            self._ensure_open()
            self._rotate_if_needed(len(line.encode(self._config.encoding)))
            self._stream.write(line)
            self._stream.flush()
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

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._stream.close()
                self._closed = True

    def __enter__(self) -> JSONFileLogger:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _open_stream(self) -> TextIO:
        return self._opener(self.path, "a", encoding=self._config.encoding, newline="")

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("logger is closed")

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        max_bytes = self._config.max_bytes
        if not max_bytes or self._config.backup_count == 0:
            return
        self._stream.seek(0, 2)
        if self._stream.tell() == 0 or self._stream.tell() + incoming_bytes <= max_bytes:
            return
        self._stream.close()
        oldest = self.path.with_name(f"{self.path.name}.{self._config.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self._config.backup_count - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            if source.exists():
                source.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
        if self.path.exists():
            self.path.replace(self.path.with_name(f"{self.path.name}.1"))
        self._stream = self._open_stream()


def create_json_logger(
    config: LoggerConfig | Mapping[str, Any] | None = None,
    /,
    *,
    clock: Callable[[], datetime] | None = None,
    opener: Callable[..., TextIO] = open,
    **overrides: Any,
) -> JSONFileLogger:
    """Public factory accepting a validated config or configuration values."""
    if config is None:
        values: dict[str, Any] = {}
    elif isinstance(config, LoggerConfig):
        if overrides:
            raise ValueError("overrides cannot be used with LoggerConfig")
        return JSONFileLogger(config, clock=clock, opener=opener)
    elif isinstance(config, Mapping):
        values = dict(config)
    else:
        raise TypeError("config must be a LoggerConfig, mapping, or None")
    values.update(overrides)
    return JSONFileLogger(LoggerConfig(**values), clock=clock, opener=opener)


def _validate_level(level: str) -> str:
    if not isinstance(level, str):
        raise TypeError("level must be a string")
    normalized = level.upper()
    if normalized not in _LEVELS:
        raise ValueError(f"unsupported log level: {level}")
    return normalized
