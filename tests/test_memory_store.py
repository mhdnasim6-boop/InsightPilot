"""Tests for MemoryStore + MemoryIndexes: CRUD and secondary-index consistency."""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.store.memory_store import MemoryStore
from backend.utils.time import utc_now


def _item(memory_id: str, memory_type: MemoryType = MemoryType.DATASET, scope: MemoryScope = MemoryScope.SESSION, tags: list[str] | None = None) -> MemoryItem:
    now = utc_now()
    return MemoryItem(
        memory_id=memory_id,
        title=f"Item {memory_id}",
        summary="summary",
        memory_type=memory_type,
        scope=scope,
        created_at=now,
        updated_at=now,
        tags=tags or [],
    )


def test_add_and_get() -> None:
    store = MemoryStore()
    item = _item("m1")
    store.add(item)
    assert store.get("m1") == item


def test_get_unknown_returns_none() -> None:
    store = MemoryStore()
    assert store.get("does-not-exist") is None


def test_list_all_most_recent_first() -> None:
    store = MemoryStore()
    store.add(_item("m1"))
    store.add(_item("m2"))
    assert [item.memory_id for item in store.list_all()] == ["m2", "m1"]


def test_update_replaces_the_item() -> None:
    store = MemoryStore()
    store.add(_item("m1"))
    updated = _item("m1").model_copy(update={"title": "Updated"})
    store.update(updated)
    assert store.get("m1").title == "Updated"  # type: ignore[union-attr]
    assert store.count() == 1


def test_delete_removes_the_item_and_returns_true() -> None:
    store = MemoryStore()
    store.add(_item("m1"))
    assert store.delete("m1") is True
    assert store.get("m1") is None


def test_delete_unknown_returns_false() -> None:
    store = MemoryStore()
    assert store.delete("does-not-exist") is False


def test_clear_empties_the_store() -> None:
    store = MemoryStore()
    store.add(_item("m1"))
    store.add(_item("m2"))
    store.clear()
    assert store.count() == 0
    assert store.list_all() == []


def test_list_by_type_filters_correctly() -> None:
    store = MemoryStore()
    store.add(_item("m1", memory_type=MemoryType.DATASET))
    store.add(_item("m2", memory_type=MemoryType.REPORT))
    assert [item.memory_id for item in store.list_by_type(MemoryType.DATASET)] == ["m1"]


def test_list_by_scope_filters_correctly() -> None:
    store = MemoryStore()
    store.add(_item("m1", scope=MemoryScope.SESSION))
    store.add(_item("m2", scope=MemoryScope.GLOBAL))
    assert [item.memory_id for item in store.list_by_scope(MemoryScope.GLOBAL)] == ["m2"]


def test_list_by_tag_filters_correctly() -> None:
    store = MemoryStore()
    store.add(_item("m1", tags=["sales"]))
    store.add(_item("m2", tags=["marketing"]))
    assert [item.memory_id for item in store.list_by_tag("sales")] == ["m1"]


def test_indexes_stay_in_sync_after_update_changes_type() -> None:
    store = MemoryStore()
    store.add(_item("m1", memory_type=MemoryType.DATASET))
    updated = _item("m1", memory_type=MemoryType.REPORT)
    store.update(updated)

    assert store.list_by_type(MemoryType.DATASET) == []
    assert [item.memory_id for item in store.list_by_type(MemoryType.REPORT)] == ["m1"]


def test_indexes_stay_in_sync_after_delete() -> None:
    store = MemoryStore()
    store.add(_item("m1", tags=["sales"]))
    store.delete("m1")
    assert store.list_by_tag("sales") == []
