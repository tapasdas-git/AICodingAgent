"""A small, standard-library JSON file logger with size-based rotation."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from os import PathLike
from pathlib import Path
from typing import Any, Callable


_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}
_RESERVED_JSON_FIELDS = frozenset({"timestamp", "level", "message", "exception"})
_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for_path(path: Path) -> threading.RLock:
    """Return the process-wide lock shared by handlers for one canonical path."""
    canonical_path = os.path.normcase(str(path.resolve()))
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(canonical_path, threading.RLock())


class _CoordinatedRotatingFileHandler(RotatingFileHandler):
    """Notice rotations performed by another handler for the same file."""

    def emit(self, record: logging.LogRecord) -> None:
        if self.stream is not None:
            try:
                path_stat = os.stat(self.baseFilename)
                stream_stat = os.fstat(self.stream.fileno())
                changed = (path_stat.st_dev, path_stat.st_ino) != (
                    stream_stat.st_dev,
                    stream_stat.st_ino,
                )
            except OSError:
                changed = True
            if changed:
                self.stream.close()
                self.stream = None
        super().emit(record)


class JsonFormatter(logging.Formatter):
    """Format each log record as one compact JSON object."""

    def __init__(self, timestamp_format: str | None = None) -> None:
        super().__init__()
        if timestamp_format is not None and not isinstance(timestamp_format, str):
            raise TypeError("timestamp_format must be a string or None")
        self.timestamp_format = timestamp_format

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, timezone.utc)
        rendered_timestamp = (
            timestamp.strftime(self.timestamp_format)
            if self.timestamp_format is not None
            else timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )
        document: dict[str, Any] = {
            "timestamp": rendered_timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_RECORD_FIELDS
                and key not in _RESERVED_JSON_FIELDS
                and not key.startswith("_")
            ):
                document[key] = value
        if record.exc_info:
            document["exception"] = self.formatException(record.exc_info)
        return json.dumps(document, ensure_ascii=False, default=_json_fallback)


def _json_fallback(value: object) -> str:
    """Represent unusual context values without dropping the whole log event."""
    try:
        return str(value)
    except Exception:
        return f"<{type(value).__name__}>"


def _parse_level(level: int | str) -> int:
    if isinstance(level, bool):
        raise TypeError("level must be an integer or a logging level name")
    if isinstance(level, int):
        if level < 0:
            raise ValueError("level must be non-negative")
        return level
    if isinstance(level, str):
        parsed = logging.getLevelName(level.upper())
        if isinstance(parsed, int):
            return parsed
        raise ValueError(f"unknown logging level: {level!r}")
    raise TypeError("level must be an integer or a logging level name")


def create_json_logger(
    log_file: str | PathLike[str],
    *,
    level: int | str = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    timestamp_format: str | None = None,
    name: str | None = None,
    handler_factory: Callable[..., logging.Handler] = _CoordinatedRotatingFileHandler,
) -> logging.Logger:
    """Create an isolated JSON logger whose writes and rotations are thread-safe."""
    if not isinstance(log_file, (str, PathLike)):
        raise TypeError("log_file must be a path")
    path = Path(log_file).expanduser()
    if not path.name:
        raise ValueError("log_file must name a file")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
        raise TypeError("max_bytes must be an integer")
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    if not isinstance(backup_count, int) or isinstance(backup_count, bool):
        raise TypeError("backup_count must be an integer")
    if backup_count < 0:
        raise ValueError("backup_count must be non-negative")
    if not callable(handler_factory):
        raise TypeError("handler_factory must be callable")

    parsed_level = _parse_level(level)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger_name = name or f"json-file:{path.resolve()}"
    logger = logging.Logger(logger_name, parsed_level)
    logger.propagate = False
    handler = handler_factory(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    # Handler.handle() holds this lock across rollover and emission. Sharing it
    # prevents separate logger instances from rotating the same path at once.
    handler.lock = _lock_for_path(path)
    handler.setLevel(parsed_level)
    handler.setFormatter(JsonFormatter(timestamp_format))
    logger.addHandler(handler)
    return logger


class JSONFileLogger:
    """Convenience facade around the logger returned by :func:`create_json_logger`."""

    def __init__(self, log_file: str | PathLike[str], **configuration: Any) -> None:
        self.logger = create_json_logger(log_file, **configuration)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.logger, name)

    def close(self) -> None:
        """Flush and close this instance's file handlers."""
        for handler in tuple(self.logger.handlers):
            handler.flush()
            handler.close()
            self.logger.removeHandler(handler)

    def __enter__(self) -> "JSONFileLogger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
