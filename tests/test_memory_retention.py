"""Tests for retention: age-based expiration, capacity-based eviction, and cleanup."""

from datetime import timedelta

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.models.retention_policy import RetentionPolicy
from backend.memory.retention.cleanup import run_cleanup
from backend.memory.retention.expiration import is_expired
from backend.memory.retention.retention_engine import RetentionEngine
from backend.memory.store.memory_store import MemoryStore
from backend.utils.time import utc_now


def _item(memory_id: str, memory_type: MemoryType = MemoryType.DATASET, importance: float = 0.5, age_days: float = 0.0) -> MemoryItem:
    created_at = utc_now() - timedelta(days=age_days)
    return MemoryItem(
        memory_id=memory_id,
        title=f"Item {memory_id}",
        summary="summary",
        memory_type=memory_type,
        scope=MemoryScope.SESSION,
        created_at=created_at,
        updated_at=created_at,
        importance=importance,
    )


def test_is_expired_with_no_max_age_never_expires() -> None:
    assert is_expired(_item("m1", age_days=1000), None) is False


def test_is_expired_true_when_older_than_max_age() -> None:
    assert is_expired(_item("m1", age_days=10), max_age_days=5) is True


def test_is_expired_false_when_within_max_age() -> None:
    assert is_expired(_item("m1", age_days=1), max_age_days=5) is False


def test_retention_engine_evicts_expired_items() -> None:
    engine = RetentionEngine()
    items = [_item("old", age_days=10), _item("new", age_days=0)]
    evicted = engine.items_to_evict(items, RetentionPolicy(max_age_days=5))
    assert evicted == ["old"]


def test_retention_engine_evicts_least_important_when_over_max_items() -> None:
    engine = RetentionEngine()
    items = [_item("low", importance=0.1), _item("mid", importance=0.5), _item("high", importance=0.9)]
    evicted = engine.items_to_evict(items, RetentionPolicy(max_items=2))
    assert evicted == ["low"]


def test_retention_engine_evicts_per_type_separately() -> None:
    engine = RetentionEngine()
    items = [
        _item("d1", memory_type=MemoryType.DATASET, importance=0.9),
        _item("d2", memory_type=MemoryType.DATASET, importance=0.1),
        _item("r1", memory_type=MemoryType.REPORT, importance=0.9),
        _item("r2", memory_type=MemoryType.REPORT, importance=0.1),
    ]
    evicted = engine.items_to_evict(items, RetentionPolicy(max_items_per_type=1))
    assert set(evicted) == {"d2", "r2"}


def test_retention_engine_with_no_policy_limits_evicts_nothing() -> None:
    engine = RetentionEngine()
    items = [_item("m1"), _item("m2")]
    assert engine.items_to_evict(items, RetentionPolicy()) == []


def test_run_cleanup_deletes_from_the_store() -> None:
    store = MemoryStore()
    store.add(_item("old", age_days=10))
    store.add(_item("new", age_days=0))

    evicted = run_cleanup(store, RetentionPolicy(max_age_days=5))

    assert evicted == ["old"]
    assert store.get("old") is None
    assert store.get("new") is not None
