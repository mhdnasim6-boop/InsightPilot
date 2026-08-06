"""DependencyResolver: resolves an ExecutionPlan's steps into a queryable dependency
graph — topological ordering, runnable-node discovery, and completion tracking.

Reuses ``backend.planning.validator.topology.topological_order()`` (Kahn's
algorithm) for both ordering *and* cycle detection — this class never
reimplements cycle detection itself, per this phase's own mandate. A plan
reaching this resolver is expected to already be validated (the same
``PlanStatus.READY`` precondition ``PlanExecutor.execute()`` enforces), so
a cyclic plan here would indicate a caller bug upstream, not something
this resolver needs to defend against a second time.
"""

from backend.execution.state.execution_state import ExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.validator.topology import topological_order

_TERMINAL = frozenset({NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED, NodeStatus.SKIPPED})
_BLOCKING = frozenset({NodeStatus.FAILED, NodeStatus.CANCELLED})
_NOT_YET_STARTED = frozenset({NodeStatus.PENDING, NodeStatus.QUEUED})


class DependencyResolver:
    """Resolves one ExecutionPlan's steps into a deterministically ordered dependency graph."""

    def __init__(self, plan: ExecutionPlan) -> None:
        self.step_order: list[str] = topological_order(plan.steps)
        self._steps_by_id = {step.step_id: step for step in plan.steps}

    def step(self, step_id: str) -> ExecutionStep:
        """Return the ExecutionStep for a step_id."""
        return self._steps_by_id[step_id]

    def dependencies_of(self, step_id: str) -> list[str]:
        """Every step_id ``step_id`` directly depends on."""
        return list(self._steps_by_id[step_id].dependencies)

    def dependents_of(self, step_id: str) -> list[str]:
        """Every step_id that directly depends on ``step_id``."""
        return [sid for sid, step in self._steps_by_id.items() if step_id in step.dependencies]

    def runnable_steps(self, state: ExecutionState) -> list[ExecutionStep]:
        """Steps not yet started whose dependencies have all COMPLETED — the next batch to dispatch."""
        runnable = []
        for step_id in self.step_order:
            node = state.steps[step_id]
            if node.status not in _NOT_YET_STARTED:
                continue
            if all(state.steps[dep].status == NodeStatus.COMPLETED for dep in self.dependencies_of(step_id)):
                runnable.append(self._steps_by_id[step_id])
        return runnable

    def unreachable_steps(self, state: ExecutionState) -> list[str]:
        """Steps that can never run because a transitive dependency FAILED/CANCELLED.

        Computed as a fixed point: a step becomes unreachable the moment
        any of its own dependencies is blocking or already unreachable,
        and that unreachability itself propagates forward to further
        dependents on the next pass.
        """
        blocked: set[str] = set()
        changed = True
        while changed:
            changed = False
            for step_id in self.step_order:
                if step_id in blocked or state.steps[step_id].status not in _NOT_YET_STARTED:
                    continue
                deps = self.dependencies_of(step_id)
                if any(state.steps[dep].status in _BLOCKING or dep in blocked for dep in deps):
                    blocked.add(step_id)
                    changed = True
        return sorted(blocked)

    def is_finished(self, state: ExecutionState) -> bool:
        """True once every step has reached a terminal status (nothing left runnable or pausable)."""
        return all(state.steps[step_id].status in _TERMINAL for step_id in self.step_order)
