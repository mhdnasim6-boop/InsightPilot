"""FileAgent endpoints: execute, list results, fetch one result.

Thin HTTP wrappers over the existing ``FileAgentService`` — no
orchestration logic here. This is the *direct* invocation path (the same
underlying ``FileAgentService`` also backs ``FileAgentNode`` inside the
orchestration graph); either path's result is fetchable through
"Get execution result" afterward.
"""

from fastapi import APIRouter, Depends

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.dependencies.file_agent import get_file_agent_service
from backend.schemas.file_agent_request import FileAgentExecuteRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/agents/file")


@router.post("/execute", response_model=SuccessResponse[AgentExecutionResult], summary="Execute the File Agent")
async def execute_file_agent(
    request: FileAgentExecuteRequest, service: FileAgentService = Depends(get_file_agent_service)
) -> SuccessResponse[AgentExecutionResult]:
    """Run FileAgent for one ExecutionStep.

    Raises ``InvalidAgentInputError`` (422) for malformed input
    (missing session or ``dataset_reference``). A downstream pipeline
    failure (bad file, cleaning error, ...) is never raised — it comes
    back as a 200 response with ``status: "failed"`` and ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    message = "File agent execution completed." if result.status.value == "completed" else "File agent execution failed."
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/executions", response_model=SuccessResponse[list[AgentExecutionResult]], summary="List File Agent executions"
)
async def list_file_agent_executions(
    service: FileAgentService = Depends(get_file_agent_service),
) -> SuccessResponse[list[AgentExecutionResult]]:
    """Return every stored FileAgent result, most recently added first."""
    return SuccessResponse.ok(data=service.list_results(), message="File agent executions fetched.")


@router.get(
    "/executions/{step_id}",
    response_model=SuccessResponse[AgentExecutionResult],
    summary="Get one File Agent execution result",
)
async def get_file_agent_execution(
    step_id: str, service: FileAgentService = Depends(get_file_agent_service)
) -> SuccessResponse[AgentExecutionResult]:
    """Fetch a previously executed step's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="File agent execution fetched.")
