"""Test configuration for importing the isolated calculator source tree."""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / "Coding"
sys.path.insert(0, str(SOURCE_DIRECTORY))
