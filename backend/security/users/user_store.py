"""UserStore: process-wide, in-memory user records — keyed by user_id, with
a username index for login lookup. Mirrors every other store added since
Phase 27 (``MemoryStore``, ``TraceStore``, ``PluginRegistry``'s own
``_records`` dict): a plain class over a private dict, no ORM, no
``BaseRepository`` — swapping in a real database later means writing a
new class with this exact same public surface.
"""

from backend.security.exceptions import DuplicateUserError, UserNotFoundError
from backend.security.users.user import User


class UserStore:
    """Name/id-addressable user storage. The only place user records live."""

    def __init__(self) -> None:
        self._users_by_id: dict[str, User] = {}
        self._id_by_username: dict[str, str] = {}

    def add(self, user: User) -> User:
        """Store a new user. Raises DuplicateUserError if the username is already taken."""
        if user.username in self._id_by_username:
            raise DuplicateUserError(f"Username '{user.username}' is already registered.")
        self._users_by_id[user.user_id] = user
        self._id_by_username[user.username] = user.user_id
        return user

    def get(self, user_id: str) -> User:
        """Fetch a user by id. Raises UserNotFoundError if unknown."""
        user = self._users_by_id.get(user_id)
        if user is None:
            raise UserNotFoundError(f"No user found for id '{user_id}'.")
        return user

    def get_by_username(self, username: str) -> User | None:
        """Fetch a user by username, or None if unregistered — never raises (used by login)."""
        user_id = self._id_by_username.get(username)
        return self._users_by_id.get(user_id) if user_id else None

    def update(self, user: User) -> User:
        """Overwrite an existing user record (same user_id/username). Raises UserNotFoundError if unknown."""
        self.get(user.user_id)
        self._users_by_id[user.user_id] = user
        return user

    def delete(self, user_id: str) -> None:
        """Remove a user. Raises UserNotFoundError if unknown."""
        user = self.get(user_id)
        del self._users_by_id[user_id]
        del self._id_by_username[user.username]

    def list(self) -> list[User]:
        """Every registered user, in registration order."""
        return list(self._users_by_id.values())

    def exists(self, username: str) -> bool:
        """Whether a user with this username is already registered."""
        return username in self._id_by_username
