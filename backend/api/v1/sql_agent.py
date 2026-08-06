"""SQLAgent endpoints: execute, fetch one result.

Thin HTTP wrappers over the existing ``SQLAgentService`` — no
orchestration logic here. This is the *direct* invocation path (the same
underlying ``SQLAgentService`` also backs ``SQLAgentNode`` inside the
orchestration graph); either path's result is fetchable through
"Get execution result" afterward — through the same shared
``AgentExecutionResultStore`` FileAgent's results already live in.

No "list executions" endpoint here, unlike ``/agents/file``: the store is
shared across agents (see ``backend/dependencies/sql_agent.py``), so a
list endpoint here would return the exact same contents
``GET /agents/file/executions`` already does — no field on
``AgentExecutionResult`` distinguishes which agent produced a result,
and adding one would mean modifying the model FileAgent already ships,
outside this phase's scope.
"""

from fastapi import APIRouter, Depends

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.dependencies.sql_agent import get_sql_agent_service
from backend.schemas.response import SuccessResponse
from backend.schemas.sql_agent_request import SQLAgentExecuteRequest

router = APIRouter(prefix="/agents/sql")


@router.post("/execute", response_model=SuccessResponse[AgentExecutionResult], summary="Execute the SQL Agent")
async def execute_sql_agent(
    request: SQLAgentExecuteRequest, service: SQLAgentService = Depends(get_sql_agent_service)
) -> SuccessResponse[AgentExecutionResult]:
    """Run SQLAgent for one ExecutionStep.

    Raises ``InvalidAgentInputError`` (422) for malformed input (missing
    session, missing/invalid connection, or not exactly one of
    ``table_name``/``query``). A downstream pipeline failure (bad
    connection, cleaning error, ...) is never raised — it comes back as
    a 200 response with ``status: "failed"`` and ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    message = "SQL agent execution completed." if result.status.value == "completed" else "SQL agent execution failed."
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/executions/{step_id}",
    response_model=SuccessResponse[AgentExecutionResult],
    summary="Get one SQL Agent execution result",
)
async def get_sql_agent_execution(
    step_id: str, service: SQLAgentService = Depends(get_sql_agent_service)
) -> SuccessResponse[AgentExecutionResult]:
    """Fetch a previously executed step's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="SQL agent execution fetched.")
