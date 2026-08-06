"""MemoryScope: what a MemoryItem is visible to.

Broadening from SESSION to GLOBAL: a SESSION memory is relevant only to
one dashboard session, USER to whichever user (once this project has
real user accounts — today, effectively a synonym for "not tied to a
single session"), PROJECT to a longer-lived body of work spanning
sessions, and GLOBAL to the whole deployment (e.g. a reusable piece of
external knowledge). Scope determines *visibility* for retrieval
filtering — it never changes how a MemoryItem is stored.
"""

from enum import Enum


class MemoryScope(str, Enum):
    """Visibility scope of one MemoryItem."""

    SESSION = "session"
    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"
