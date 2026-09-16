"""Make the isolated calculator source directory importable in tests."""

from __future__ import annotations

import sys
from pathlib import Path

TASK_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_DIRECTORY))
