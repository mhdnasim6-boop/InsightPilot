"""Chat endpoint: ask a question about the current dataset/analysis/visualization/plan.

A thin HTTP wrapper over the existing ``ChatService`` — no business logic
here. The request body carries the full ``ChatContext`` because the
backend is stateless with respect to conversation history: the frontend
assembles it fresh from its own session state on every turn.
"""

from fastapi import APIRouter, Depends

from backend.chatbot.response.models import ChatResponse
from backend.chatbot.services.chat_service import ChatService
from backend.dependencies.chatbot import get_chat_service
from backend.schemas.chat_request import ChatRequest
from backend.schemas.response import SuccessResponse

router = APIRouter()


@router.post(
    "/chat",
    response_model=SuccessResponse[ChatResponse],
    summary="Ask a question about the current dataset, analysis, visualization, or plan",
)
async def ask_chat(
    request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)
) -> SuccessResponse[ChatResponse]:
    """Answer ``request.question`` using ``request.context`` as the only knowledge source."""
    response = await chat_service.ask(request.question, request.context)
    return SuccessResponse.ok(data=response, message="Answer generated.")
