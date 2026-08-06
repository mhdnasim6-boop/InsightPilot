"""ExecutionTaskRegistry: tracks the in-flight asyncio.Task backing each currently
running/resuming execution, keyed by execution_id.

Mirrors ``ExecutionEngine``'s own ``self._tasks`` exactly
(``backend.orchestration.execution.engine``). A dedicated, independently
cached singleton — not a field on ``ExecutionService`` itself — for the
same reason ``ExecutionCheckpoint`` now carries the originating ``plan``:
``ExecutionService`` is deliberately left uncached (a stateless wrapper,
matching ``FileAgentService``/every other agent service), so anything
that must genuinely persist across requests has to live in its own
cached store instead of a per-instance dict.
"""

import asyncio

from backend.execution.state.execution_state import ExecutionState


class ExecutionTaskRegistry:
    """Process-wide registry of in-flight execution tasks, keyed by execution_id."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[ExecutionState]] = {}

    def register(self, execution_id: str, task: "asyncio.Task[ExecutionState]") -> None:
        """Track ``task`` as the in-flight run backing ``execution_id``."""
        self._tasks[execution_id] = task

    def get(self, execution_id: str) -> "asyncio.Task[ExecutionState] | None":
        """Return the in-flight task for ``execution_id``, or None if none is tracked."""
        return self._tasks.get(execution_id)

    def discard(self, execution_id: str) -> None:
        """Stop tracking ``execution_id``'s task (it has settled, one way or another)."""
        self._tasks.pop(execution_id, None)
