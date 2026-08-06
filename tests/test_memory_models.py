"""Tests for the memory domain models: immutability, defaults, and reuse."""

import pytest
from pydantic import ValidationError

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_result import MemoryResult
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.memory.models.memory_type import MemoryType
from backend.memory.models.retention_policy import RetentionPolicy
from backend.utils.time import utc_now


def _item(**overrides: object) -> MemoryItem:
    now = utc_now()
    defaults: dict[str, object] = {
        "memory_id": "m1",
        "title": "Test",
        "summary": "A test memory.",
        "memory_type": MemoryType.DATASET,
        "scope": MemoryScope.SESSION,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)  # type: ignore[arg-type]


def test_memory_item_is_frozen() -> None:
    item = _item()
    with pytest.raises(ValidationError):
        item.title = "changed"  # type: ignore[misc]


def test_memory_item_defaults() -> None:
    item = _item()
    assert item.content == {}
    assert item.tags == []
    assert item.importance == 0.5
    assert item.references == []
    assert item.metadata == {}


def test_memory_item_importance_bounds() -> None:
    with pytest.raises(ValidationError):
        _item(importance=1.5)
    with pytest.raises(ValidationError):
        _item(importance=-0.1)


def test_memory_reference_is_frozen() -> None:
    ref = MemoryReference(reference_type="dataset", reference_id="d1")
    with pytest.raises(ValidationError):
        ref.reference_id = "d2"  # type: ignore[misc]


def test_memory_query_defaults() -> None:
    query = MemoryQuery()
    assert query.keyword is None
    assert query.tags == []
    assert query.memory_type is None
    assert query.scope is None
    assert query.top_k is None
    assert query.recent_first is True


def test_memory_result_defaults() -> None:
    result = MemoryResult()
    assert result.items == []
    assert result.total_matched == 0
    assert result.query is None


def test_retention_policy_defaults_to_no_limits() -> None:
    policy = RetentionPolicy()
    assert policy.max_items is None
    assert policy.max_items_per_type is None
    assert policy.max_age_days is None


def test_memory_statistics_defaults() -> None:
    stats = MemoryStatistics()
    assert stats.total_items == 0
    assert stats.by_type == {}
    assert stats.by_scope == {}
    assert stats.oldest_item_at is None
