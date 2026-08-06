"""Execution endpoints: start/resume/cancel a DAG execution, and inspect its
state, progress, and graph.

Thin HTTP wrappers only — every endpoint here is a direct call into
``ExecutionService``, never a parallel implementation. ``resume``/
``cancel`` take ``execution_id`` as a path parameter
(``/execution/{execution_id}/resume``), matching this codebase's own
``/approvals/plan/{plan_id}/resume`` convention.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.execution import get_execution_service
from backend.execution.progress.progress_tracker import ProgressSnapshot
from backend.execution.services.execution_service import ExecutionService
from backend.execution.state.execution_state import ExecutionState
from backend.schemas.execution_request import ExecutionStartRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/execution")


@router.post("/start", response_model=SuccessResponse[ExecutionState], summary="Start a DAG execution")
async def start_execution(
    request: ExecutionStartRequest, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[ExecutionState]:
    """Execute a READY ExecutionPlan as a dependency-aware, parallel DAG.

    Raises PlanNotReadyError (409) if the plan isn't READY. Returns
    ``status=paused`` (not completed) if a step's node requires approval
    under the active ApprovalPolicy.
    """
    state = await execution_service.start(request.plan, request.session_id)
    return SuccessResponse.ok(data=state, message=f"Execution '{state.execution_id}' — status: {state.status.value}.")


@router.post(
    "/{execution_id}/resume", response_model=SuccessResponse[ExecutionState], summary="Resume a paused execution"
)
async def resume_execution(
    execution_id: str, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[ExecutionState]:
    """Resume a PAUSED execution. Raises ExecutionNotPausedError (409) if it isn't paused."""
    state = await execution_service.resume(execution_id)
    message = "Execution resumed and completed." if state.status.value == "completed" else "Execution paused again."
    return SuccessResponse.ok(data=state, message=message)


@router.post(
    "/{execution_id}/cancel", response_model=SuccessResponse[ExecutionState], summary="Cancel an execution"
)
async def cancel_execution(
    execution_id: str, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[ExecutionState]:
    """Cancel every currently running/queued/paused/pending step. Completed steps are untouched.

    Raises ExecutionNotFoundError (404) if unknown. If the execution is
    still genuinely in flight, this only requests cancellation — poll
    ``GET /execution/{execution_id}`` shortly after for the fully
    settled CANCELLED state.
    """
    state = execution_service.cancel(execution_id)
    return SuccessResponse.ok(data=state, message=f"Execution '{execution_id}' cancellation requested.")


@router.get("/{execution_id}", response_model=SuccessResponse[ExecutionState], summary="Get one execution's state")
async def get_execution(
    execution_id: str, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[ExecutionState]:
    """Fetch an execution's current state. Raises ExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=execution_service.get(execution_id), message="Execution fetched.")


@router.get(
    "/{execution_id}/progress", response_model=SuccessResponse[ProgressSnapshot], summary="Get execution progress"
)
async def get_execution_progress(
    execution_id: str, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[ProgressSnapshot]:
    """Fetch an execution's current progress — percent complete and per-status step lists."""
    return SuccessResponse.ok(data=execution_service.get_progress(execution_id), message="Progress fetched.")


@router.get("/{execution_id}/graph", response_model=SuccessResponse[str], summary="Get execution graph as Mermaid")
async def get_execution_graph(
    execution_id: str, execution_service: ExecutionService = Depends(get_execution_service)
) -> SuccessResponse[str]:
    """Fetch the plan's Mermaid flowchart, each step highlighted by its current status."""
    return SuccessResponse.ok(data=execution_service.get_graph(execution_id), message="Graph fetched.")
