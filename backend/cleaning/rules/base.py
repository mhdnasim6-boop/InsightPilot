"""Common interface every cleaning rule must implement.

Mirrors ``backend.orchestration.nodes.base.OrchestrationNode``: only the
methods that genuinely differ per rule (``validate``/``apply``/
``description``) are abstract; ``rollback()`` has a working default,
because the ``CleaningPipeline`` always holds the pre-rule DataFrame and
can hand it back without any rule needing to know how to "undo" itself.

Rules are independent by design: none of the built-in rules assume
another rule has already run, and the pipeline never orders them based on
inter-rule coupling — only the order they were registered in.
"""

from abc import ABC, abstractmethod

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord


class CleaningRule(ABC):
    """Contract every cleaning rule (built-in or future) must satisfy."""

    name: str

    @abstractmethod
    def validate(self, dataframe: pd.DataFrame) -> bool:
        """Return whether this rule has anything meaningful to do on the given DataFrame."""

    @abstractmethod
    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        """Apply this rule, returning the resulting DataFrame and a record of what changed."""

    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this rule does."""

    def rollback(self, dataframe: pd.DataFrame, original: pd.DataFrame) -> pd.DataFrame:
        """Undo this rule's effect. Default: return the pre-rule snapshot the pipeline held."""
        return original
