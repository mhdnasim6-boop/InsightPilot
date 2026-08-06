"""In-memory trace_id -> ExecutionTrace store, plus plan-scoped lookup.

Mirrors ``ApprovalStore``/every other ``*Store`` in this codebase — a
plain dict, process-wide singleton via DI, no persistence backend yet.
Only ever holds *finalized* (frozen) traces; in-progress traces live in
``ObservabilityService``'s own private accumulator and are never put
here until ``finalize_trace()``.
"""

from backend.observability.models.execution_trace import ExecutionTrace


class TraceStore:
    """Process-wide store of finalized ExecutionTraces, keyed by trace_id."""

    def __init__(self) -> None:
        self._traces: dict[str, ExecutionTrace] = {}

    def put(self, trace: ExecutionTrace) -> None:
        """Store (or overwrite) a trace, keyed by its own ``trace_id``."""
        self._traces[trace.trace_id] = trace

    def get(self, trace_id: str) -> ExecutionTrace | None:
        """Return the trace for a trace_id, or None if not present."""
        return self._traces.get(trace_id)

    def list_all(self) -> list[ExecutionTrace]:
        """Return every stored trace, most recently added first."""
        return list(reversed(self._traces.values()))

    def list_for_plan(self, plan_id: str) -> list[ExecutionTrace]:
        """Return every finalized trace for a given plan, most recently added first."""
        return [trace for trace in self.list_all() if trace.plan_id == plan_id]
