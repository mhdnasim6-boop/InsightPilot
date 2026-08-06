"""JWTService: issues and verifies HS256 JWTs via PyJWT — access tokens
(short-lived, stateless, no ``jti``) and refresh tokens (longer-lived,
carry a ``jti`` so SessionManager can track/revoke them).

Clock skew: ``jwt.decode()``'s own ``leeway`` parameter is used directly
— PyJWT's documented mechanism for tolerating a verifier's clock running
a little ahead/behind the issuer's, rather than hand-rolling a manual
``exp`` comparison.
"""

from datetime import UTC, datetime, timedelta

import jwt
from loguru import logger

from backend.security.exceptions import InvalidTokenError, TokenExpiredError
from backend.security.models.token import Token, TokenClaims, TokenType
from backend.security.users.user import User
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_INSECURE_DEFAULT_SECRET = "insecure-dev-secret-change-me-in-production"


class JWTService:
    """Encodes/decodes access and refresh JWTs for one signing key/algorithm."""

    def __init__(
        self, secret_key: str, algorithm: str, access_expire_minutes: int,
        refresh_expire_minutes: int, clock_skew_seconds: int,
    ) -> None:
        if secret_key == _INSECURE_DEFAULT_SECRET:
            logger.warning(
                "JWTService is using the insecure default jwt_secret_key — "
                "set JWT_SECRET_KEY before running in production."
            )
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_minutes = refresh_expire_minutes
        self._clock_skew_seconds = clock_skew_seconds

    def create_access_token(self, user: User) -> Token:
        """Issue a short-lived access token. No ``jti`` — access tokens are pure
        stateless bearer credentials, never tracked in SessionManager."""
        return self._issue(user, TokenType.ACCESS, self._access_expire_minutes, jti=None)

    def create_refresh_token(self, user: User) -> Token:
        """Issue a refresh token with a fresh ``jti`` — the caller (AuthenticationService)
        registers that ``jti`` with SessionManager so logout can later revoke it."""
        return self._issue(user, TokenType.REFRESH, self._refresh_expire_minutes, jti=generate_id())

    def decode(self, token: str, expected_type: TokenType) -> TokenClaims:
        """Verify signature/expiry and return the claims. Raises TokenExpiredError or
        InvalidTokenError (signature/structure/wrong-token-type)."""
        try:
            payload = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm], leeway=self._clock_skew_seconds,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("Token has expired.") from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(f"Token could not be verified: {exc}") from exc

        try:
            claims = TokenClaims(
                sub=payload["sub"], username=payload["username"], role=payload["role"],
                token_type=TokenType(payload["token_type"]), jti=payload.get("jti"),
                issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            )
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError(f"Token payload is malformed: {exc}") from exc

        if claims.token_type != expected_type:
            raise InvalidTokenError(f"Expected a {expected_type.value} token, got a {claims.token_type.value} token.")
        return claims

    def _issue(self, user: User, token_type: TokenType, expire_minutes: int, jti: str | None) -> Token:
        issued_at = utc_now()
        expires_at = issued_at + timedelta(minutes=expire_minutes)
        payload = {
            "sub": user.user_id, "username": user.username, "role": user.role.value,
            "token_type": token_type.value, "iat": int(issued_at.timestamp()), "exp": int(expires_at.timestamp()),
        }
        if jti is not None:
            payload["jti"] = jti
        value = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return Token(value=value, token_type=token_type, expires_at=expires_at)
