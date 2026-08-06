"""Common interface every chart generator must implement.

Mirrors ``backend.cleaning.rules.base.CleaningRule``: ``applicable()`` is a
cheap pre-check with a human-readable reason (used by the recommendation
engine to explain what it skipped and why); ``generate()`` does the real
work and is only ever called when ``applicable()`` returned True.
"""

from abc import ABC, abstractmethod

from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.context import ChartContext


class ChartGenerator(ABC):
    """Contract every chart generator (built-in or future) must satisfy."""

    chart_type: ChartType

    @abstractmethod
    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        """Return whether this generator can produce a chart from ``context``.

        The second element is a human-readable reason — populated when
        not applicable, ``None`` when applicable.
        """

    @abstractmethod
    def generate(self, context: ChartContext) -> ChartSpecification:
        """Generate the chart. Only ever called when ``applicable()`` returned True."""
