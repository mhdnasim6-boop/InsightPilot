"""Recursively converts pandas/numpy values into plain, JSON-serializable
Python values — needed because ``BusinessDataset.sample_rows`` and
``.statistics`` are ``Any``-typed dicts that must round-trip through
``model_dump_json()`` cleanly.
"""

import math
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    """Convert one value (possibly nested) into a JSON-safe Python value."""
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    return value
