"""Planner endpoints: generate, preview, validate, explain, and execute an ExecutionPlan.

Thin HTTP wrappers only. Generate/Execute go through the existing
``PlannerAgentService``/``PlanningService`` — the same objects
``PlannerAgentNode``/``OrchestrationService`` themselves use — never a
parallel implementation. Preview/Validate/Explain are stateless reshapes
of a POSTed ``ExecutionPlan``, so they work identically for a
freshly-generated plan or one a user edited by hand before approving it.
"""

from fastapi import APIRouter, Depends

from backend.agents.planner.exceptions import PlanValidationFailedError
from backend.agents.planner.models.result import PlannerAgentResult
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.dependencies.orchestration import get_planner_agent_service
from backend.dependencies.planning import get_planning_service
from backend.planning.models.plan import ExecutionPlan
from backend.schemas.planner_agent_request import (
    PlanActionRequest,
    PlannerAgentExecuteRequest,
)
from backend.schemas.planner_plan_views import (
    PlanExplanation,
    PlanPreview,
    PlanValidationResponse,
)
from backend.schemas.response import SuccessResponse
from backend.services.planning_service import PlanningService

router = APIRouter(prefix="/planner")


@router.post("/plan", response_model=SuccessResponse[PlannerAgentResult], summary="Generate an ExecutionPlan")
async def generate_plan(
    request: PlannerAgentExecuteRequest, service: PlannerAgentService = Depends(get_planner_agent_service)
) -> SuccessResponse[PlannerAgentResult]:
    """Run PlannerAgent for one ExecutionStep, with dynamically discovered agents.

    Raises ``InvalidPlannerAgentInputError`` (422) for malformed input
    (missing ``user_request``). A planning failure (malformed AI
    response, or a plan that fails validation) is never raised — it
    comes back as a 200 response with ``status: "failed"`` and
    ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    message = "Plan generated." if result.status.value == "completed" else "Plan generation failed."
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/plan/{step_id}", response_model=SuccessResponse[PlannerAgentResult], summary="Get one Planner execution result"
)
async def get_plan_execution(
    step_id: str, service: PlannerAgentService = Depends(get_planner_agent_service)
) -> SuccessResponse[PlannerAgentResult]:
    """Fetch a previously generated plan's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="Planner execution fetched.")


@router.post("/preview", response_model=SuccessResponse[PlanPreview], summary="Preview an ExecutionPlan")
async def preview_plan(
    request: PlanActionRequest, service: PlanningService = Depends(get_planning_service)
) -> SuccessResponse[PlanPreview]:
    """Render a plan as a Mermaid flowchart, JSON, and a linear timeline — all at once."""
    preview = PlanPreview(
        mermaid=service.export_mermaid(request.plan),
        json_export=service.export_json(request.plan),
        timeline=service.export_timeline(request.plan),
    )
    return SuccessResponse.ok(data=preview, message="Plan preview generated.")


@router.post("/validate", response_model=SuccessResponse[PlanValidationResponse], summary="Validate an ExecutionPlan")
async def validate_plan(
    request: PlanActionRequest, service: PlanningService = Depends(get_planning_service)
) -> SuccessResponse[PlanValidationResponse]:
    """Structurally validate a plan against the live orchestration graph's registered nodes."""
    validated_plan, validation_result = await service.validate(request.plan)
    response = PlanValidationResponse(plan=validated_plan, validation=validation_result)
    message = "Plan is valid." if validation_result.is_valid else "Plan failed validation."
    return SuccessResponse.ok(data=response, message=message)


@router.post("/explain", response_model=SuccessResponse[PlanExplanation], summary="Explain an ExecutionPlan")
async def explain_plan(request: PlanActionRequest) -> SuccessResponse[PlanExplanation]:
    """Explain why each step's agent was selected, using each step's own description.

    Stateless — works for a freshly-generated plan or one a user edited
    by hand, since the explanation is read straight off the plan itself.
    """
    return SuccessResponse.ok(data=PlanExplanation.from_plan(request.plan), message="Plan explained.")


@router.post("/execute", response_model=SuccessResponse[ExecutionPlan], summary="Approve and execute an ExecutionPlan")
async def execute_plan(
    request: PlanActionRequest, service: PlanningService = Depends(get_planning_service)
) -> SuccessResponse[ExecutionPlan]:
    """Register, validate, optimize, and execute a plan via PlanningService.

    Raises ``PlanValidationFailedError`` (422) if the plan doesn't pass
    validation — execution never proceeds on a plan that wouldn't
    already be accepted by ``POST /planner/validate``.
    """
    registered = await service.register(request.plan)
    validated_plan, validation_result = await service.validate(registered)
    if not validation_result.is_valid:
        raise PlanValidationFailedError(
            f"Plan '{request.plan.plan_id}' failed validation and cannot be executed.", detail=validation_result
        )
    optimized_plan = service.optimize(validated_plan)
    executed_plan = await service.execute(optimized_plan)
    return SuccessResponse.ok(data=executed_plan, message="Plan executed.")
