"""Tests for deterministic retrieval: keyword/tag search, similarity, and
RetrievalEngine's combined filter + ranking + top-k behavior.
"""

from datetime import datetime, timedelta
from typing import Any

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.retrieval.keyword_search import keyword_match_count, keyword_matches
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.retrieval.similarity import word_overlap_score
from backend.memory.retrieval.tag_search import matches_any_tag, tag_match_count
from backend.utils.time import utc_now


def _item(
    memory_id: str,
    title: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    importance: float = 0.5,
    created_at: datetime | None = None,
    memory_type: MemoryType = MemoryType.DATASET,
    scope: MemoryScope = MemoryScope.SESSION,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    now = created_at or utc_now()
    return MemoryItem(
        memory_id=memory_id,
        title=title or f"Item {memory_id}",
        summary=summary,
        memory_type=memory_type,
        scope=scope,
        created_at=now,
        updated_at=now,
        tags=tags or [],
        importance=importance,
        metadata=metadata or {},
    )


def test_keyword_matches_is_case_insensitive_substring() -> None:
    item = _item("m1", title="Sales Dataset", summary="Quarterly revenue figures")
    assert keyword_matches(item, "SALES") is True
    assert keyword_matches(item, "revenue") is True
    assert keyword_matches(item, "marketing") is False


def test_keyword_matches_empty_keyword_matches_everything() -> None:
    item = _item("m1", title="Anything")
    assert keyword_matches(item, "") is True
    assert keyword_matches(item, "   ") is True


def test_keyword_match_count_counts_occurrences() -> None:
    item = _item("m1", title="sales sales", summary="sales report")
    assert keyword_match_count(item, "sales") == 3


def test_tag_matching() -> None:
    item = _item("m1", tags=["Sales", "Q1"])
    assert matches_any_tag(item, ["sales"]) is True
    assert matches_any_tag(item, ["marketing"]) is False
    assert matches_any_tag(item, []) is True
    assert tag_match_count(item, ["sales", "q1", "marketing"]) == 2


def test_word_overlap_score_is_jaccard_similarity() -> None:
    assert word_overlap_score("the quick brown fox", "the quick fox") == 3 / 4
    assert word_overlap_score("", "anything") == 0.0
    assert word_overlap_score("completely different", "no overlap here") == 0.0
    assert word_overlap_score("same words here", "same words here") == 1.0


def test_retrieval_engine_filters_by_type_and_scope() -> None:
    engine = RetrievalEngine()
    items = [
        _item("m1", memory_type=MemoryType.DATASET, scope=MemoryScope.SESSION),
        _item("m2", memory_type=MemoryType.REPORT, scope=MemoryScope.SESSION),
        _item("m3", memory_type=MemoryType.DATASET, scope=MemoryScope.GLOBAL),
    ]
    result = engine.retrieve(items, MemoryQuery(memory_type=MemoryType.DATASET, scope=MemoryScope.SESSION))
    assert [item.memory_id for item in result.items] == ["m1"]


def test_retrieval_engine_filters_by_session_id_in_metadata() -> None:
    engine = RetrievalEngine()
    items = [
        _item("m1", metadata={"session_id": "s1"}),
        _item("m2", metadata={"session_id": "s2"}),
    ]
    result = engine.retrieve(items, MemoryQuery(session_id="s1"))
    assert [item.memory_id for item in result.items] == ["m1"]


def test_retrieval_engine_filters_by_importance() -> None:
    engine = RetrievalEngine()
    items = [_item("low", importance=0.2), _item("high", importance=0.9)]
    result = engine.retrieve(items, MemoryQuery(min_importance=0.5))
    assert [item.memory_id for item in result.items] == ["high"]


def test_retrieval_engine_filters_by_date_range() -> None:
    engine = RetrievalEngine()
    now = utc_now()
    items = [
        _item("old", created_at=now - timedelta(days=10)),
        _item("new", created_at=now),
    ]
    result = engine.retrieve(items, MemoryQuery(date_from=now - timedelta(days=1)))
    assert [item.memory_id for item in result.items] == ["new"]


def test_retrieval_engine_ranks_keyword_matches_above_recency_alone() -> None:
    engine = RetrievalEngine()
    now = utc_now()
    items = [
        _item("recent_no_match", title="Unrelated", created_at=now),
        _item("older_match", title="Sales dataset", created_at=now - timedelta(days=5)),
    ]
    result = engine.retrieve(items, MemoryQuery(keyword="sales"))
    assert result.items[0].memory_id == "older_match"


def test_retrieval_engine_top_k_truncates_but_reports_total_matched() -> None:
    engine = RetrievalEngine()
    items = [_item(f"m{i}") for i in range(5)]
    result = engine.retrieve(items, MemoryQuery(top_k=2))
    assert len(result.items) == 2
    assert result.total_matched == 5


def test_retrieval_engine_recent_first_orders_by_created_at_when_no_other_signal() -> None:
    engine = RetrievalEngine()
    now = utc_now()
    items = [
        _item("older", created_at=now - timedelta(days=1)),
        _item("newer", created_at=now),
    ]
    result = engine.retrieve(items, MemoryQuery())
    assert [item.memory_id for item in result.items] == ["newer", "older"]
