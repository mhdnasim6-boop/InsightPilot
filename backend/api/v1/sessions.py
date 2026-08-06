"""Session endpoints: lightweight, unauthenticated session creation.

Thin HTTP wrappers over the existing ``SessionService`` — no new business
logic. The dashboard creates one session per browser session to
correlate uploads against.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.services import get_session_service
from backend.models.session import Session
from backend.schemas.response import SuccessResponse
from backend.services.session_service import SessionService

router = APIRouter()


@router.post("/sessions", response_model=SuccessResponse[Session], summary="Create a new dashboard session")
async def create_session(service: SessionService = Depends(get_session_service)) -> SuccessResponse[Session]:
    """Create a new session for the dashboard to correlate subsequent requests against."""
    session = service.create_session()
    return SuccessResponse.ok(data=session, message="Session created.")


@router.get("/sessions/{session_id}", response_model=SuccessResponse[Session], summary="Fetch a session")
async def get_session(
    session_id: str, service: SessionService = Depends(get_session_service)
) -> SuccessResponse[Session]:
    """Fetch a session by ID. Raises NotFoundError (404) if it doesn't exist."""
    session = service.get_session(session_id)
    return SuccessResponse.ok(data=session, message="Session fetched.")
