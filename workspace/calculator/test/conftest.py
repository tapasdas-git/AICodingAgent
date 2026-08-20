"""Ensure the repository package is importable in isolated test runs."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))
