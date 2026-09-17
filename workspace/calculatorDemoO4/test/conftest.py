"""Make the isolated calculator source importable during local tests."""

from pathlib import Path
import sys


SOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / "Coding"
sys.path.insert(0, str(SOURCE_DIRECTORY))
