"""Closed vocabulary for a Planner-estimated plan complexity."""

from enum import Enum


class ComplexityLevel(str, Enum):
    """How complex the Planner judges a generated plan to be."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
