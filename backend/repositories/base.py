"""Generic repository contract shared by every entity-specific repository."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityT = TypeVar("EntityT")
IdT = TypeVar("IdT")


class BaseRepository(ABC, Generic[EntityT, IdT]):
    """Storage-agnostic CRUD contract.

    Concrete implementations may be in-memory (as used now) or backed by
    a real database later; callers depend only on this interface.
    """

    @abstractmethod
    def add(self, entity: EntityT) -> EntityT:
        """Persist a new entity and return it."""

    @abstractmethod
    def get(self, entity_id: IdT) -> EntityT | None:
        """Return an entity by ID, or None if it doesn't exist."""

    @abstractmethod
    def update(self, entity: EntityT) -> EntityT:
        """Persist changes to an existing entity and return it."""

    @abstractmethod
    def delete(self, entity_id: IdT) -> bool:
        """Remove an entity by ID. Returns True if it existed."""

    @abstractmethod
    def list(self) -> list[EntityT]:
        """Return every stored entity."""
