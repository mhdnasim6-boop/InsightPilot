"""SessionManager: tracks one Session per issued refresh token, so
"logout" — impossible to do to a stateless JWT itself — genuinely means
something: removing that token's session from the allowlist.

Access tokens are never tracked here (see JWTService's own docstring) —
only refresh tokens get a ``jti``/Session, which keeps every ordinary
request's authentication check pure/stateless while still making logout
and refresh-token rotation real.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.security.exceptions import TokenRevokedError
from backend.utils.time import utc_now


class Session(BaseModel):
    """One active (or revoked) refresh-token session."""

    model_config = ConfigDict(frozen=True)

    session_id: str  # == the refresh token's own jti claim
    user_id: str
    created_at: datetime
    expires_at: datetime
    revoked: bool = False


class SessionManager:
    """Process-wide, in-memory session registry, keyed by session_id (refresh token jti)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, session_id: str, user_id: str, expires_at: datetime) -> Session:
        """Register a new active session for a freshly issued refresh token."""
        session = Session(session_id=session_id, user_id=user_id, created_at=utc_now(), expires_at=expires_at)
        self._sessions[session_id] = session
        return session

    def require_active(self, session_id: str) -> Session:
        """Fetch a session and confirm it's genuinely usable. Raises TokenRevokedError if
        it was logged out, rotated away, or was never registered (an unknown jti is
        treated identically to a revoked one — a caller can't tell the difference)."""
        session = self._sessions.get(session_id)
        if session is None or session.revoked:
            raise TokenRevokedError("This refresh token's session has been revoked or does not exist.")
        return session

    def revoke(self, session_id: str) -> None:
        """Revoke one session (logout, or refresh-token rotation). A no-op if already revoked/unknown."""
        session = self._sessions.get(session_id)
        if session is not None:
            self._sessions[session_id] = session.model_copy(update={"revoked": True})

    def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke every active session belonging to one user (e.g. on account deactivation)."""
        for session_id, session in list(self._sessions.items()):
            if session.user_id == user_id and not session.revoked:
                self.revoke(session_id)

    def list_active_for_user(self, user_id: str) -> list[Session]:
        """Every currently-active session for one user."""
        return [s for s in self._sessions.values() if s.user_id == user_id and not s.revoked]
