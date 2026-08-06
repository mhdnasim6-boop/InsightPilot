"""Workflow endpoints: create/list/get, execute/pause/resume/cancel/clone,
statistics, and the dependency graph (Mermaid) — thin wrappers over
``WorkflowService``, exactly like every other router in this codebase.
"""

from fastapi import APIRouter, Depends

from backend.core.exceptions import ValidationError
from backend.dependencies.workflows import get_workflow_service
from backend.schemas.response import SuccessResponse
from backend.schemas.workflow_request import (
    CloneWorkflowRequest,
    CreateWorkflowRequest,
    ExecuteWorkflowRequest,
)
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import require_permission
from backend.security.models.authenticated_user import AuthenticatedUser
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_statistics import WorkflowStatistics
from backend.workflows.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows")


@router.post("", response_model=SuccessResponse[Workflow], summary="Create a workflow")
async def create_workflow(
    body: CreateWorkflowRequest,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[Workflow]:
    """Create a workflow either from a natural-language ``objective`` (the real PlannerAgent
    plans it) or from explicit ``name``/``steps`` (an authored workflow)."""
    if body.objective:
        workflow = await service.create_from_objective(body.objective, body.session_id, body.tags)
    elif body.name and body.steps:
        workflow = service.create_from_steps(body.name, body.description, body.steps, body.tags)
    else:
        raise ValidationError("Either 'objective', or both 'name' and 'steps', must be given.")
    return SuccessResponse.ok(data=workflow, message=f"Workflow '{workflow.definition.name}' created.")


@router.get("", response_model=SuccessResponse[list[Workflow]], summary="List workflows")
async def list_workflows(
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[Workflow]]:
    """Every known workflow, oldest first."""
    return SuccessResponse.ok(data=service.list_workflows(), message="Workflows fetched.")


@router.get("/{workflow_id}", response_model=SuccessResponse[Workflow], summary="Get one workflow")
async def get_workflow(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[Workflow]:
    """Fetch one workflow by id. Raises WorkflowNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get(workflow_id), message="Workflow fetched.")


@router.post(
    "/{workflow_id}/execute", response_model=SuccessResponse[WorkflowExecution], summary="Execute a workflow"
)
async def execute_workflow(
    workflow_id: str, body: ExecuteWorkflowRequest,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[WorkflowExecution]:
    """Validate, optimize, and run a workflow end-to-end via the real ExecutionService."""
    execution = await service.execute(workflow_id, body.session_id)
    return SuccessResponse.ok(data=execution, message="Workflow execution started.")


@router.post("/{workflow_id}/pause", response_model=SuccessResponse[WorkflowExecution], summary="Pause a workflow")
async def pause_workflow(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[WorkflowExecution]:
    """Voluntarily pause a workflow's latest (running) execution."""
    latest = service.get_latest_execution(workflow_id)
    paused = await service.pause(latest.workflow_execution_id)
    return SuccessResponse.ok(data=paused, message="Workflow paused.")


@router.post("/{workflow_id}/resume", response_model=SuccessResponse[WorkflowExecution], summary="Resume a workflow")
async def resume_workflow(
    workflow_id: str, body: ExecuteWorkflowRequest,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[WorkflowExecution]:
    """Resume a workflow's latest (paused) execution."""
    latest = service.get_latest_execution(workflow_id)
    resumed = await service.resume(latest.workflow_execution_id, body.session_id)
    return SuccessResponse.ok(data=resumed, message="Workflow resumed.")


@router.post("/{workflow_id}/cancel", response_model=SuccessResponse[WorkflowExecution], summary="Cancel a workflow")
async def cancel_workflow(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[WorkflowExecution]:
    """Cancel a workflow's latest (running or paused) execution outright."""
    latest = service.get_latest_execution(workflow_id)
    cancelled = service.cancel(latest.workflow_execution_id)
    return SuccessResponse.ok(data=cancelled, message="Workflow cancelled.")


@router.post("/{workflow_id}/clone", response_model=SuccessResponse[Workflow], summary="Clone a workflow")
async def clone_workflow(
    workflow_id: str, body: CloneWorkflowRequest,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_PLANS)),
) -> SuccessResponse[Workflow]:
    """Create a fresh, DRAFT copy of a workflow's definition."""
    cloned = service.clone(workflow_id, body.new_name)
    return SuccessResponse.ok(data=cloned, message=f"Workflow cloned as '{cloned.definition.name}'.")


@router.get(
    "/{workflow_id}/statistics", response_model=SuccessResponse[WorkflowStatistics], summary="Workflow statistics"
)
async def get_workflow_statistics(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[WorkflowStatistics]:
    """Aggregate execution counts/durations for one workflow."""
    return SuccessResponse.ok(data=service.statistics(workflow_id), message="Workflow statistics fetched.")


@router.get("/{workflow_id}/graph", response_model=SuccessResponse[str], summary="Workflow dependency graph")
async def get_workflow_graph(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[str]:
    """The workflow's dependency graph as Mermaid — status-highlighted once it has run."""
    return SuccessResponse.ok(data=service.get_graph(workflow_id), message="Workflow graph generated.")
