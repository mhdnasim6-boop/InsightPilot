"""The swappable plan-optimization contract."""

from abc import ABC, abstractmethod

from backend.planning.models.plan import ExecutionPlan


class PlanOptimizer(ABC):
    """Contract every plan optimizer (default or future) must satisfy."""

    @abstractmethod
    def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Return an optimized copy of the given plan."""
