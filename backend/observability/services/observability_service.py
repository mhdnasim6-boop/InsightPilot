"""ObservabilityService: owns every in-progress plan's mutable trace accumulator
and produces immutable ExecutionTrace snapshots on demand.

Mirrors the mutable-accumulator/immutable-final-model pattern already
used by ``PlanExecutor``'s own ``_PausedExecution`` (Phase 23): a
private ``_TraceBuilder`` dataclass collects agent/tool/AI/approval
records while a plan runs; ``finalize_trace()`` freezes it into an
``ExecutionTrace`` the moment the plan reaches a terminal
``PlanStatus``. ``get_trace()``/``list_traces()`` can also return a
frozen *snapshot* of a still-running builder — each snapshot is an
immutable fact about the trace's state at the moment it was requested,
never a handle callers can mutate; the builder behind it stays the only
place that ever changes.

Optional collaborator throughout the call chain (``PlanExecutor``,
``AIService``, ``TracingTool`` all accept it as ``| None``) — exactly
like ``approval_service``/``checkpointer`` before it, so nothing about
tracing is required for the rest of the system to keep working.

Correlation with tool calls and AI calls happens via
``backend.observability.context`` contextvars rather than explicit
parameters, since tool/AI calls happen many layers below
``PlanExecutor`` (inside whatever agent service the graph node calls)
with no existing channel to pass a trace_id down through.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from backend.approval.models.approval import ExecutionApproval
from backend.observability.context import current_trace_id
from backend.observability.exceptions import TraceNotFoundError
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


@dataclass
class _TraceBuilder:
    """Mutable accumulator for one in-progress plan's trace. Never exposed directly."""

    trace_id: str
    plan_id: str
    session_id: str | None
    start_time: datetime
    status: PlanStatus = PlanStatus.RUNNING
    agent_traces: list[AgentTrace] = field(default_factory=list)
    tool_traces: list[ToolTrace] = field(default_factory=list)
    ai_calls: list[AICallTrace] = field(default_factory=list)
    approval_traces: list[ExecutionApproval] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recorded_agent_keys: set[str] = field(default_factory=set)


class ObservabilityService:
    """Runs the full lifecycle of an ExecutionTrace: start, record, finalize, query."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store
        self._in_progress: dict[str, _TraceBuilder] = {}
        self._trace_id_by_plan: dict[str, str] = {}

    def start_trace(self, plan_id: str, session_id: str | None = None) -> str:
        """Begin a new trace for a plan's execution. Returns the new trace_id."""
        trace_id = generate_id()
        self._in_progress[trace_id] = _TraceBuilder(
            trace_id=trace_id, plan_id=plan_id, session_id=session_id, start_time=utc_now()
        )
        self._trace_id_by_plan[plan_id] = trace_id
        return trace_id

    def trace_id_for_plan(self, plan_id: str) -> str | None:
        """The trace_id already started for a plan, if any — lets callers avoid re-starting on resume."""
        return self._trace_id_by_plan.get(plan_id)

    def mark_status(self, trace_id: str, status: PlanStatus) -> None:
        """Update an in-progress trace's status (e.g. to PAUSED) without finalizing it."""
        builder = self._in_progress.get(trace_id)
        if builder is not None:
            builder.status = status

    def set_approvals(self, trace_id: str, approvals: list[ExecutionApproval]) -> None:
        """Replace an in-progress trace's approval records with the plan's current full list."""
        builder = self._in_progress.get(trace_id)
        if builder is not None:
            builder.approval_traces = list(approvals)

    def record_step(
        self, trace_id: str | None, step_id: str, artifacts: dict[str, Any], variables: dict[str, Any]
    ) -> None:
        """Build one AgentTrace per not-yet-recorded '<node_name>_result' artifact.

        Every agent result already carries ``step_id``/``status``/
        ``warnings``/``execution_time``/``metadata`` — no new
        instrumentation, just reading what ``state.artifacts`` already
        has after a step settles (``artifacts``/``variables`` are
        ``PlanExecutor``'s own ``step.outputs``/``step.inputs``, which
        mirror ``InsightPilotState.artifacts``/``.variables`` exactly).
        Deduplicated per (step_id, agent_name) so a step that
        pauses/resumes through several approval gates never records the
        same node's contribution twice.
        """
        if trace_id is None:
            return
        builder = self._in_progress.get(trace_id)
        if builder is None:
            return

        end_time = utc_now()
        input_size = len(json.dumps(variables, default=str))
        for key, value in artifacts.items():
            if not key.endswith("_result") or not isinstance(value, dict):
                continue
            agent_name = key.removesuffix("_result")
            dedup_key = f"{step_id}:{agent_name}"
            if dedup_key in builder.recorded_agent_keys:
                continue
            builder.recorded_agent_keys.add(dedup_key)

            execution_time = float(value.get("execution_time") or 0.0)
            status = ExecutionStatus(value.get("status") or ExecutionStatus.COMPLETED.value)
            tool_calls = [t.tool_name for t in builder.tool_traces if t.agent_name == agent_name]
            builder.agent_traces.append(
                AgentTrace(
                    agent_name=agent_name,
                    start_time=end_time - timedelta(seconds=execution_time),
                    end_time=end_time,
                    duration_ms=execution_time * 1000,
                    status=status,
                    input_size=input_size,
                    output_size=len(json.dumps(value, default=str)),
                    tool_calls=tool_calls,
                    metadata=dict(value.get("metadata") or {}),
                )
            )
            builder.warnings.extend(value.get("warnings") or [])

    def record_tool_trace(self, tool_trace: ToolTrace) -> None:
        """Record one tool call. Reads ``current_trace_id`` — a no-op if unset (untraced context)."""
        builder = self._in_progress.get(current_trace_id.get() or "")
        if builder is not None:
            builder.tool_traces.append(tool_trace)

    def record_ai_call(self, ai_trace: AICallTrace) -> None:
        """Record one AI provider call. Reads ``current_trace_id`` — a no-op if unset."""
        builder = self._in_progress.get(current_trace_id.get() or "")
        if builder is not None:
            builder.ai_calls.append(ai_trace)

    def record_error(self, trace_id: str | None, error: str) -> None:
        """Attach an error message to an in-progress trace."""
        if trace_id is None:
            return
        builder = self._in_progress.get(trace_id)
        if builder is not None:
            builder.errors.append(error)

    def finalize_trace(
        self, trace_id: str, status: PlanStatus, approval_traces: list[ExecutionApproval] | None = None
    ) -> ExecutionTrace:
        """Freeze an in-progress trace into an immutable ExecutionTrace and store it.

        Raises TraceNotFoundError if ``trace_id`` has no in-progress
        builder (already finalized, or never started).
        """
        builder = self._in_progress.pop(trace_id, None)
        if builder is None:
            raise TraceNotFoundError(f"No in-progress trace found for trace_id '{trace_id}'.")
        end_time = utc_now()
        trace = ExecutionTrace(
            trace_id=builder.trace_id,
            plan_id=builder.plan_id,
            session_id=builder.session_id,
            start_time=builder.start_time,
            end_time=end_time,
            duration_ms=(end_time - builder.start_time).total_seconds() * 1000,
            status=status,
            agent_traces=list(builder.agent_traces),
            tool_traces=list(builder.tool_traces),
            approval_traces=list(approval_traces if approval_traces is not None else builder.approval_traces),
            ai_calls=list(builder.ai_calls),
            errors=list(builder.errors),
            warnings=list(builder.warnings),
        )
        self._store.put(trace)
        return trace

    def get_trace(self, trace_id: str) -> ExecutionTrace:
        """Fetch a trace — a live snapshot if still running, the frozen record otherwise.

        Raises TraceNotFoundError if unknown either way.
        """
        builder = self._in_progress.get(trace_id)
        if builder is not None:
            return self._snapshot(builder)
        trace = self._store.get(trace_id)
        if trace is None:
            raise TraceNotFoundError(f"No trace found for trace_id '{trace_id}'.")
        return trace

    def get_trace_for_plan(self, plan_id: str) -> ExecutionTrace:
        """Fetch the trace for a plan_id. Raises TraceNotFoundError if the plan never started one."""
        trace_id = self._trace_id_by_plan.get(plan_id)
        if trace_id is None:
            raise TraceNotFoundError(f"No trace found for plan_id '{plan_id}'.")
        return self.get_trace(trace_id)

    def list_traces(self) -> list[ExecutionTrace]:
        """Every trace, in-progress snapshots first (most recently started), then finalized ones."""
        live = [self._snapshot(builder) for builder in reversed(list(self._in_progress.values()))]
        return live + self._store.list_all()

    def _snapshot(self, builder: _TraceBuilder) -> ExecutionTrace:
        return ExecutionTrace(
            trace_id=builder.trace_id,
            plan_id=builder.plan_id,
            session_id=builder.session_id,
            start_time=builder.start_time,
            end_time=None,
            duration_ms=None,
            status=builder.status,
            agent_traces=list(builder.agent_traces),
            tool_traces=list(builder.tool_traces),
            approval_traces=list(builder.approval_traces),
            ai_calls=list(builder.ai_calls),
            errors=list(builder.errors),
            warnings=list(builder.warnings),
        )
