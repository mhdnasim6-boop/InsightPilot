"""BrowserAgent endpoints: execute, fetch one result.

Thin HTTP wrappers over the existing ``BrowserAgentService`` — no
orchestration logic here. This is the *direct* invocation path (the same
underlying ``BrowserAgentService`` also backs ``BrowserAgentNode`` inside
the orchestration graph).

Only the two endpoints the task requires ("Execute Browser Agent",
"Retrieve execution result") are exposed — unlike FileAgent's
``/executions`` list endpoint, this isn't a redundancy argument (Browser
has its own, separate ``BrowserAgentResultStore``, not shared with
File/SQLAgent's), simply matching the requested scope.
"""

from fastapi import APIRouter, Depends

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.dependencies.browser_agent import get_browser_agent_service
from backend.schemas.browser_agent_request import BrowserAgentExecuteRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/agents/browser")


@router.post(
    "/execute", response_model=SuccessResponse[BrowserAgentResult], summary="Execute the Browser Agent"
)
async def execute_browser_agent(
    request: BrowserAgentExecuteRequest, service: BrowserAgentService = Depends(get_browser_agent_service)
) -> SuccessResponse[BrowserAgentResult]:
    """Run BrowserAgent for one ExecutionStep.

    Raises ``InvalidAgentInputError`` (422) for malformed input (missing
    session, or a present ``search_request``/``companies``/
    ``industries``/``products``/``keywords`` field with the wrong
    shape). A step with none of those fields present returns a 200 with
    ``status: "skipped"`` — not an error. A search failure is never
    raised either — it comes back as a 200 with ``status: "failed"``
    and ``warnings``.
    """
    result = await service.execute_step(request.step, request.session_id)
    messages = {
        "completed": "Browser agent execution completed.",
        "skipped": "Browser agent execution skipped: no search-relevant input present.",
    }
    message = messages.get(result.status.value, "Browser agent execution failed.")
    return SuccessResponse.ok(data=result, message=message)


@router.get(
    "/executions/{step_id}",
    response_model=SuccessResponse[BrowserAgentResult],
    summary="Get one Browser Agent execution result",
)
async def get_browser_agent_execution(
    step_id: str, service: BrowserAgentService = Depends(get_browser_agent_service)
) -> SuccessResponse[BrowserAgentResult]:
    """Fetch a previously executed step's result. Raises AgentExecutionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_result(step_id), message="Browser agent execution fetched.")
