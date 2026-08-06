"""Token / TokenType / TokenClaims: the shapes JWTService issues and decodes."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TokenType(str, Enum):
    """A JWT's own ``token_type`` claim — access tokens and refresh tokens are never
    interchangeable; JWTService.decode() always checks this against what the caller expected."""

    ACCESS = "access"
    REFRESH = "refresh"


class Token(BaseModel):
    """One issued JWT, ready to hand back to a client."""

    model_config = ConfigDict(frozen=True)

    value: str
    token_type: TokenType
    expires_at: datetime


class TokenClaims(BaseModel):
    """A decoded, verified JWT's payload — never constructed except by ``JWTService.decode()``."""

    model_config = ConfigDict(frozen=True)

    sub: str  # user_id
    username: str
    role: str
    token_type: TokenType
    issued_at: datetime
    expires_at: datetime
    jti: str | None = None  # present on refresh tokens only — see SessionManager
