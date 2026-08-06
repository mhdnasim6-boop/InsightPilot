"""FederationCoordinator: wraps WorkflowService, routing each execute() call to a
cluster before delegating — the one place federation actually touches real execution.

**Why the real workflow always still runs locally.** This process has no
message broker or RPC transport (out of scope for this phase — "all
communication is represented as routing decisions only"). A
``RoutingDecision`` records *which cluster the workload is credited to*;
it never ships anything anywhere. So regardless of whether the selected
cluster is the local one or a registered remote one,
``self._inner.execute()`` — the real, unmodified ``WorkflowService`` —
is what actually runs, in-process, exactly as it always has. This
mirrors ``backend.distributed.scheduler.dispatch_scheduler.DispatchingAgentService``'s
own exact reasoning (Phase 38) one layer up: the decorator decides *credit*,
never *where computation happens*.

Only ``execute()`` is wrapped — never ``resume()``/``cancel()``: "already-
running work remains owned by its original cluster," so resuming a
paused workflow must never re-route it to a different cluster. Every
other method (including ``resume()``) is forwarded unchanged via
``__getattr__``, the same shape
``backend.realtime.publishers.workflow_publisher.RealtimePublishingWorkflowService``
already established in Phase 37.

A `WorkflowExecution` that comes back PAUSED (approval-gated) still
closes out its RemoteExecution/RoutingDecision as "complete" — this
`execute()` *call* finished without raising, which is what closes the
cluster's own credit in this synchronous, in-process model; resuming
later is a separate, unrouted call. A documented simplification, not an
oversight — see this phase's own README section for the full reasoning.
"""

from typing import Any

from backend.federation.coordination.workload_router import WorkloadRouter
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.services.workflow_service import WorkflowService


class FederationCoordinator:
    """Wraps a real WorkflowService, routing each execute() call to a credited cluster."""

    def __init__(self, inner: WorkflowService, workload_router: WorkloadRouter) -> None:
        self._inner = inner
        self._workload_router = workload_router

    async def execute(self, workflow_id: str, session_id: str | None = None) -> WorkflowExecution:
        workflow = self._inner.get(workflow_id)
        required_agents = sorted({step.node_name for step in workflow.definition.steps})
        step_count = len(workflow.definition.steps)

        decision, remote_execution = self._workload_router.route(workflow_id, required_agents, step_count)
        try:
            execution = await self._inner.execute(workflow_id, session_id)
        except Exception as exc:
            self._workload_router.finish(decision.decision_id, remote_execution.remote_execution_id, success=False, error=str(exc))
            raise
        self._workload_router.finish(decision.decision_id, remote_execution.remote_execution_id, success=True)
        return execution

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
