"""UserService: the only public entry point for user management —
create/get/list/update/delete, credential verification, and first-run
admin bootstrap. Nothing outside this module touches UserStore directly.
"""

from loguru import logger

from backend.security.authentication.password_hasher import PasswordHasher
from backend.security.authorization.role import Role
from backend.security.exceptions import DuplicateUserError
from backend.security.users.profile import UserProfile
from backend.security.users.user import User
from backend.security.users.user_store import UserStore
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_INSECURE_DEFAULT_PASSWORD = "ChangeMe123!"


class UserService:
    """Create/get/list/update/delete users; verify login credentials."""

    def __init__(self, store: UserStore, password_hasher: PasswordHasher) -> None:
        self._store = store
        self._password_hasher = password_hasher

    def create_user(
        self, username: str, email: str, password: str, role: Role, full_name: str = "",
    ) -> User:
        """Create and store a new user. Raises DuplicateUserError if the username is taken."""
        now = utc_now()
        user = User(
            user_id=generate_id(), username=username, email=email, full_name=full_name,
            hashed_password=self._password_hasher.hash(password), role=role,
            is_active=True, created_at=now, updated_at=now,
        )
        return self._store.add(user)

    def get(self, user_id: str) -> User:
        """Fetch one user by id. Raises UserNotFoundError if unknown."""
        return self._store.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        """Fetch one user by username, or None. Never raises — used by login, where a
        not-found user must be indistinguishable from a wrong password (see InvalidCredentialsError)."""
        return self._store.get_by_username(username)

    def list_users(self) -> list[UserProfile]:
        """Every registered user's public profile."""
        return [UserProfile.from_user(user) for user in self._store.list()]

    def update_user(
        self, user_id: str, *, email: str | None = None, full_name: str | None = None,
        role: Role | None = None, is_active: bool | None = None, password: str | None = None,
    ) -> User:
        """Update one or more fields of an existing user. Raises UserNotFoundError if unknown."""
        current = self._store.get(user_id)
        updated = current.model_copy(
            update={
                "email": email if email is not None else current.email,
                "full_name": full_name if full_name is not None else current.full_name,
                "role": role if role is not None else current.role,
                "is_active": is_active if is_active is not None else current.is_active,
                "hashed_password": self._password_hasher.hash(password) if password else current.hashed_password,
                "updated_at": utc_now(),
            }
        )
        return self._store.update(updated)

    def delete_user(self, user_id: str) -> None:
        """Delete a user. Raises UserNotFoundError if unknown."""
        self._store.delete(user_id)

    def verify_credentials(self, username: str, password: str) -> User | None:
        """Return the matching, active User, or None for any failure (unknown username,
        wrong password, or a disabled account) — the caller (AuthenticationService)
        decides which SecurityError that None becomes."""
        user = self._store.get_by_username(username)
        if user is None or not user.is_active:
            return None
        if not self._password_hasher.verify(password, user.hashed_password):
            return None
        return user

    def ensure_default_admin(self, username: str, password: str) -> None:
        """Idempotently seed a first-run Admin account if no users exist yet.

        Called once, from ``backend.dependencies.security.get_user_service()``
        at singleton construction — a fresh InsightPilot instance would
        otherwise have no way to log in at all. Logs a loud warning if the
        recognizable insecure default password is still in effect, so an
        operator sees it at startup rather than discovering it later.
        """
        if self._store.list():
            return
        try:
            self.create_user(username=username, email=f"{username}@insightpilot.local", password=password, role=Role.ADMIN, full_name="Administrator")
        except DuplicateUserError:
            return
        if password == _INSECURE_DEFAULT_PASSWORD:
            logger.warning(
                "Bootstrapped admin user '{}' with the default insecure password — "
                "set SECURITY_ADMIN_PASSWORD before running in production.", username,
            )
        else:
            logger.info("Bootstrapped admin user '{}'.", username)
