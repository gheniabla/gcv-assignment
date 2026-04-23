"""Pytest discovery helper.

Adds the project root to sys.path so `from library import ...` works in tests/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
