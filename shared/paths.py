"""Filesystem paths shared across backend, frontend, and config.

Computed once here so nothing else in the project re-derives the project
root from ``__file__`` independently (and risks drifting if the layout
ever changes depth).
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
