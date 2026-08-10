"""Small cross-platform advisory lock used for task-state updates."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


def _lock(handle: BinaryIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI
        import msvcrt

        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock(handle: BinaryIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def task_state_lock(todo_path: Path) -> Iterator[None]:
    """Serialize read-modify-write operations for one TODO directory."""
    lock_path = todo_path.parent / ".mycodeagent-task-state.lock"
    with lock_path.open("a+b") as lock_file:
        _lock(lock_file)
        try:
            yield
        finally:
            _unlock(lock_file)
