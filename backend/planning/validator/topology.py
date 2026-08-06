"""Dependency-graph algorithm shared by the validator and the default optimizer."""

from backend.planning.models.step import ExecutionStep


class CycleDetectedError(Exception):
    """Internal signal raised by ``topological_order`` when steps form a cycle.

    Caught by ``PlanValidator`` and reported as a ``ValidationIssue`` — not
    meant to escape this package as a raw exception.
    """


def topological_order(steps: list[ExecutionStep]) -> list[str]:
    """Return step_ids in a valid execution order (Kahn's algorithm).

    Dependencies on a step_id not present in ``steps`` are ignored here —
    reporting missing dependencies is ``PlanValidator``'s job, not this
    function's. Ties are broken alphabetically for deterministic output.
    """
    known_ids = {step.step_id for step in steps}
    in_degree = {step.step_id: 0 for step in steps}
    dependents: dict[str, list[str]] = {step.step_id: [] for step in steps}

    for step in steps:
        for dependency in step.dependencies:
            if dependency not in known_ids:
                continue
            in_degree[step.step_id] += 1
            dependents[dependency].append(step.step_id)

    ready = sorted(step_id for step_id, degree in in_degree.items() if degree == 0)
    order: list[str] = []

    while ready:
        current = ready.pop(0)
        order.append(current)
        for dependent in sorted(dependents[current]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
        ready.sort()

    if len(order) != len(steps):
        cyclic = known_ids - set(order)
        raise CycleDetectedError(f"Cyclic dependency detected among steps: {sorted(cyclic)}")

    return order
