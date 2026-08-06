"""WorkflowDependencyGraph: ordering, cycle detection, structural parallel-
batch preview, and dynamic insert/remove over a WorkflowStep list.

Reuses ``backend.planning.validator.topology.topological_order()``
directly for both ordering and cycle detection — never a second Kahn's-
algorithm implementation. The only genuinely new logic here is
``parallel_batches()`` (grouping steps into rounds that *could* run
together, a purely structural preview computed before any execution
starts) and the dynamic-insert/remove helpers the task names — neither
duplicates anything ``DependencyResolver``/``DAGScheduler`` already do at
actual *runtime* dispatch time.
"""

from backend.planning.models.plan import ExecutionStep
from backend.planning.validator.topology import CycleDetectedError, topological_order
from backend.workflows.exceptions import WorkflowCycleError
from backend.workflows.models.workflow_step import WorkflowStep


def to_execution_steps(steps: list[WorkflowStep]) -> list[ExecutionStep]:
    """Convert WorkflowSteps into real ExecutionSteps — a pure, lossless structural
    mapping (no logic of its own), what every actual validation/optimization/
    execution call in this package hands to the existing planning/execution engines."""
    return [
        ExecutionStep(
            step_id=step.step_id, name=step.name, description=step.description, node_name=step.node_name,
            inputs=step.inputs, dependencies=step.dependencies, retry_policy=step.retry_policy,
            timeout=step.timeout,
        )
        for step in steps
    ]


class WorkflowDependencyGraph:
    """Structural operations over a WorkflowStep list — no execution, no I/O."""

    def order(self, steps: list[WorkflowStep]) -> list[str]:
        """Valid execution order (step_ids), via the existing topological_order(). Raises
        WorkflowCycleError (translated from topological_order()'s own CycleDetectedError)
        if the steps contain a dependency cycle."""
        try:
            return topological_order(to_execution_steps(steps))
        except CycleDetectedError as exc:
            raise WorkflowCycleError(str(exc)) from exc

    def parallel_batches(self, steps: list[WorkflowStep]) -> list[list[str]]:
        """Group step_ids into ordered rounds that could run in parallel — a structural
        preview only (the real DAGScheduler makes the actual runtime dispatch decision)."""
        remaining = {step.step_id: set(step.dependencies) for step in steps}
        batches: list[list[str]] = []
        while remaining:
            ready = sorted(step_id for step_id, deps in remaining.items() if not deps)
            if not ready:
                missing = sorted(remaining)
                raise WorkflowCycleError(f"Dependency cycle detected among step(s): {missing}")
            batches.append(ready)
            for step_id in ready:
                del remaining[step_id]
            for deps in remaining.values():
                deps.difference_update(ready)
        return batches

    def validate_dependencies(self, steps: list[WorkflowStep]) -> list[str]:
        """Every dependency id referenced by some step but absent from ``steps`` itself."""
        known = {step.step_id for step in steps}
        missing = {dep for step in steps for dep in step.dependencies if dep not in known}
        return sorted(missing)

    def insert_step(self, steps: list[WorkflowStep], new_step: WorkflowStep) -> list[WorkflowStep]:
        """Insert (or replace, by step_id) a step. Raises WorkflowCycleError if this
        insertion would create a cycle — the step list is left untouched in that case."""
        remaining = [step for step in steps if step.step_id != new_step.step_id]
        updated = [*remaining, new_step]
        self.order(updated)
        return updated

    def remove_step(self, steps: list[WorkflowStep], step_id: str) -> list[WorkflowStep]:
        """Remove a step by id, and strip it from every other step's own dependencies —
        removal never leaves a dangling reference behind."""
        updated = [step for step in steps if step.step_id != step_id]
        return [
            step.model_copy(update={"dependencies": [dep for dep in step.dependencies if dep != step_id]})
            for step in updated
        ]
