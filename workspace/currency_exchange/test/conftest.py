"""Make the isolated application modules importable for task-local tests."""

from pathlib import Path
import sys


CODING_DIRECTORY = Path(__file__).resolve().parents[1] / "Coding"
sys.path.insert(0, str(CODING_DIRECTORY))
