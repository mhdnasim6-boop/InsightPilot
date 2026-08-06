"""ExecutiveSummaryAgent endpoints: execute, fetch one result.

Thin HTTP wrappers over the existing ``ExecutiveSummaryService`` — no
reasoning logic here. This is the *direct* invocation path (the same
underlying ``ExecutiveSummaryService`` also backs
``ExecutiveSummaryAgentNode`` inside the orchestration graph). Only the
two endpoints the task requires are exposed; ExecutiveSummaryAgent has
its own, separate ``ExecutiveSummaryResultStore``, so a "list
executions" endpoint would add nothing no other endpoint already
provides — it simply matches the requested scope.
"""

from fastapi import APIRouter, Depends

from backend.agents.executive_summary.models.result import ExecutiveSummaryResult
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.dependencies.executive_summary import get_executive_summary_service
from backend.schemas.executive_summary_request import ExecutiveSummaryExecuteRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/agents/executive-summary")


@router.post(
    "/execute", response_model=SuccessResponse[ExecutiveSummaryResult], summary="Execute the Executive Summary Agent"
)
async def execute_executive_summary_agent(
    request: ExecutiveSummaryExecuteRequest, service: ExecutiveSummaryService = Depends(get_executive_summary_service)
) -> SuccessResponse[ExecutiveSummaryResult]:
    """Run ExecutiveSummaryAgent for one ExecutionStep.

    Raises ``InvalidAgentInputError`` (422) for malformed input (missing
    session/report_document, or a present field with the wrong shape).
    A bad AI call, or a response that doesn't parse into the expected
    schema, is never raised — it comes back as a 200 response with
    ``status: "failed"`` and ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    message = (
        "Executive summary execution completed."
        if result.status.value == "completed"
        else "Executive summary execution failed."
    )
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/executions/{step_id}",
    response_model=SuccessResponse[ExecutiveSummaryResult],
    summary="Get one Executive Summary Agent execution result",
)
async def get_executive_summary_execution(
    step_id: str, service: ExecutiveSummaryService = Depends(get_executive_summary_service)
) -> SuccessResponse[ExecutiveSummaryResult]:
    """Fetch a previously executed step's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="Executive summary execution fetched.")
