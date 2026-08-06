"""Collaboration endpoints: start a session (with its first delegation), run/
resume/cancel it, and inspect its state, history, and aggregate statistics.

Thin HTTP wrappers only — every endpoint here is a direct call into
``CollaborationService``, never a parallel implementation. Route order
matters: ``/collaboration/statistics`` is registered before
``/collaboration/{collaboration_id}`` so FastAPI matches it as a literal
path segment rather than treating "statistics" as a collaboration_id
(same reasoning as ``/memory/statistics`` vs. ``/memory/{memory_id}``).
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_statistics import (
    CollaborationStatistics,
)
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.collaboration.services.collaboration_service import CollaborationService
from backend.dependencies.collaboration import get_collaboration_service
from backend.schemas.collaboration_request import (
    CollaborationDelegateRequest,
    CollaborationStartRequest,
)
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/collaboration")


@router.get("/statistics", response_model=SuccessResponse[CollaborationStatistics], summary="Get collaboration statistics")
async def get_collaboration_statistics(
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
) -> SuccessResponse[CollaborationStatistics]:
    """Aggregate counts across every tracked collaboration session."""
    return SuccessResponse.ok(data=collaboration_service.statistics(), message="Statistics fetched.")


@router.get("/capabilities", response_model=SuccessResponse[list[dict[str, Any]]], summary="List agent capabilities")
async def list_capabilities(
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
) -> SuccessResponse[list[dict[str, Any]]]:
    """Every registered agent's declared inputs/outputs/tools/cost/duration."""
    capabilities = [capability.model_dump(mode="json") for capability in collaboration_service.discover_capabilities()]
    return SuccessResponse.ok(data=capabilities, message="Capabilities fetched.")


@router.post("/start", response_model=SuccessResponse[CollaborationTask], summary="Start a collaboration session")
async def start_collaboration(
    request: CollaborationStartRequest, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[CollaborationTask]:
    """Create a new collaboration session for a high-level goal and delegate its first SubTask.

    Does not execute anything yet — call ``POST /collaboration/{id}/run``
    next to actually run it.
    """
    task = collaboration_service.create_session(
        CollaborationRequest(goal=request.goal, session_id=request.session_id, context=request.context)
    )
    collaboration_service.delegate(
        task.collaboration_id, request.assigned_agent, request.description, request.inputs, reason=request.reason
    )
    task = collaboration_service.get(task.collaboration_id)
    return SuccessResponse.ok(data=task, message=f"Collaboration '{task.collaboration_id}' started.")


@router.post("/{collaboration_id}/delegate", response_model=SuccessResponse[SubTask], summary="Delegate one more SubTask")
async def delegate_subtask(
    collaboration_id: str,
    request: CollaborationDelegateRequest,
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
) -> SuccessResponse[SubTask]:
    """Assign a new SubTask (or reuse an existing equivalent one) within an already-started session."""
    subtask = collaboration_service.delegate(
        collaboration_id, request.assigned_agent, request.description, request.inputs, request.dependencies, request.reason
    )
    return SuccessResponse.ok(data=subtask, message=f"SubTask '{subtask.subtask_id}' delegated to '{subtask.assigned_agent}'.")


@router.post("/{collaboration_id}/run", response_model=SuccessResponse[CollaborationTask], summary="Run a collaboration session")
async def run_collaboration(
    collaboration_id: str, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[CollaborationTask]:
    """Run every currently-ready (and dynamically spawned) subtask to completion or a pause."""
    task = await collaboration_service.run(collaboration_id)
    return SuccessResponse.ok(data=task, message=f"Collaboration '{collaboration_id}' — status: {task.status.value}.")


@router.post(
    "/{collaboration_id}/resume", response_model=SuccessResponse[CollaborationTask], summary="Resume a paused session"
)
async def resume_collaboration(
    collaboration_id: str, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[CollaborationTask]:
    """Resume a PAUSED collaboration session (after approval), then keep driving it."""
    task = await collaboration_service.resume(collaboration_id)
    return SuccessResponse.ok(data=task, message=f"Collaboration '{collaboration_id}' — status: {task.status.value}.")


@router.post("/{collaboration_id}/cancel", response_model=SuccessResponse[CollaborationTask], summary="Cancel a session")
async def cancel_collaboration(
    collaboration_id: str, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[CollaborationTask]:
    """Cancel a collaboration session outright."""
    task = collaboration_service.cancel(collaboration_id)
    return SuccessResponse.ok(data=task, message=f"Collaboration '{collaboration_id}' cancelled.")


@router.get("/{collaboration_id}", response_model=SuccessResponse[CollaborationTask], summary="Get one collaboration session")
async def get_collaboration(
    collaboration_id: str, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[CollaborationTask]:
    """Fetch a collaboration session's current task graph. Raises CollaborationNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=collaboration_service.get(collaboration_id), message="Collaboration fetched.")


@router.get(
    "/{collaboration_id}/history", response_model=SuccessResponse[dict[str, Any]], summary="Get a session's message/delegation history"
)
async def get_collaboration_history(
    collaboration_id: str, collaboration_service: CollaborationService = Depends(get_collaboration_service)
) -> SuccessResponse[dict[str, Any]]:
    """Every message, delegation, negotiation, and artifact exchange for one session."""
    history = collaboration_service.history(collaboration_id)
    return SuccessResponse.ok(
        data={key: [item.model_dump(mode="json") for item in items] for key, items in history.items()},
        message="History fetched.",
    )
