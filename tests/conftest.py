"""Minimal conftest — adds src/ to sys.path for editable-style imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
