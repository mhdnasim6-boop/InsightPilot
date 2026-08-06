"""ReportAgent endpoints: execute, fetch one result.

Thin HTTP wrappers over the existing ``ReportAgentService`` — no
reporting logic here. This is the *direct* invocation path (the same
underlying ``ReportAgentService`` also backs ``ReportAgentNode`` inside
the orchestration graph). Only the two endpoints the task requires are
exposed; ReportAgent has its own, separate ``ReportAgentResultStore`` —
`GET /api/v1/reports` (existing, unrelated) already lists every
``ReportDocument`` ever built regardless of which agent built it, so a
"list executions" endpoint here would only duplicate that.
"""

from fastapi import APIRouter, Depends

from backend.agents.report.models.result import ReportAgentResult
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.dependencies.report_agent import get_report_agent_service
from backend.schemas.report_agent_request import ReportAgentExecuteRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/agents/report")


@router.post("/execute", response_model=SuccessResponse[ReportAgentResult], summary="Execute the Report Agent")
async def execute_report_agent(
    request: ReportAgentExecuteRequest, service: ReportAgentService = Depends(get_report_agent_service)
) -> SuccessResponse[ReportAgentResult]:
    """Run ReportAgent for one ExecutionStep.

    Raises ``InvalidAgentInputError`` (422) for malformed input (missing
    session/dataset, a present field with the wrong shape, or an
    unrecognized ``report_config.template_type``). A report-building
    failure is never raised — it comes back as a 200 response with
    ``status: "failed"`` and ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    message = "Report agent execution completed." if result.status.value == "completed" else "Report agent execution failed."
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/executions/{step_id}",
    response_model=SuccessResponse[ReportAgentResult],
    summary="Get one Report Agent execution result",
)
async def get_report_agent_execution(
    step_id: str, service: ReportAgentService = Depends(get_report_agent_service)
) -> SuccessResponse[ReportAgentResult]:
    """Fetch a previously executed step's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="Report agent execution fetched.")
