"""Tests for MemoryService: the single public entry point — remember/recall/
forget/search/summarize/statistics/export/clear/apply_retention — plus
observability integration (every operation traced via the existing
ObservabilityService, no new tracing mechanism).
"""

import pytest

from backend.memory.exceptions import MemoryItemNotFoundError
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.models.retention_policy import RetentionPolicy
from backend.memory.services.memory_service import MemoryService
from backend.observability.context import agent_context, trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore


def test_remember_creates_a_retrievable_item() -> None:
    service = MemoryService()
    item = service.remember("Title", "Summary", MemoryType.DATASET)
    assert service.recall(item.memory_id) == item


def test_remember_uses_defaults() -> None:
    service = MemoryService()
    item = service.remember("Title", "Summary", MemoryType.DECISION)
    assert item.scope == MemoryScope.SESSION
    assert item.importance == 0.5
    assert item.tags == []


def test_recall_raises_for_unknown_id() -> None:
    service = MemoryService()
    with pytest.raises(MemoryItemNotFoundError):
        service.recall("does-not-exist")


def test_forget_returns_true_when_deleted_false_otherwise() -> None:
    service = MemoryService()
    item = service.remember("Title", "Summary", MemoryType.DATASET)
    assert service.forget(item.memory_id) is True
    assert service.forget(item.memory_id) is False


def test_list_all_returns_every_memory_most_recent_first() -> None:
    service = MemoryService()
    first = service.remember("First", "s1", MemoryType.DATASET)
    second = service.remember("Second", "s2", MemoryType.DATASET)
    assert [item.memory_id for item in service.list_all()] == [second.memory_id, first.memory_id]


def test_search_filters_and_ranks() -> None:
    service = MemoryService()
    service.remember("Sales dataset", "Q1 sales", MemoryType.DATASET)
    service.remember("Marketing report", "Q1 marketing", MemoryType.REPORT)
    result = service.search(MemoryQuery(keyword="sales"))
    assert len(result.items) == 1
    assert result.items[0].title == "Sales dataset"


def test_summarize_all_memories() -> None:
    service = MemoryService()
    service.remember("First", "s1", MemoryType.DATASET)
    service.remember("Second", "s2", MemoryType.DATASET)
    summary = service.summarize()
    assert "First" in summary
    assert "Second" in summary


def test_summarize_conversation_type_uses_conversation_summary() -> None:
    service = MemoryService()
    service.remember("Chat turn", "answer", MemoryType.CONVERSATION, tags=["kpi"])
    summary = service.summarize(MemoryQuery(memory_type=MemoryType.CONVERSATION))
    assert "prior exchange" in summary


def test_statistics_reflect_current_store_contents() -> None:
    service = MemoryService()
    service.remember("A", "a", MemoryType.DATASET, importance=0.4)
    service.remember("B", "b", MemoryType.REPORT, importance=0.8)
    stats = service.statistics()
    assert stats.total_items == 2
    assert stats.by_type == {"dataset": 1, "report": 1}
    assert stats.average_importance == pytest.approx(0.6)


def test_export_json_and_markdown() -> None:
    service = MemoryService()
    service.remember("Title", "Summary", MemoryType.DATASET)
    assert '"title": "Title"' in service.export("json")
    assert "# Memory Export" in service.export("markdown")
    assert "## Title" in service.export("markdown")


def test_clear_removes_everything() -> None:
    service = MemoryService()
    service.remember("Title", "Summary", MemoryType.DATASET)
    service.clear()
    assert service.list_all() == []


def test_apply_retention_evicts_per_policy() -> None:
    service = MemoryService()
    for i in range(5):
        service.remember(f"Item {i}", "s", MemoryType.DATASET, importance=i / 10)
    evicted = service.apply_retention(RetentionPolicy(max_items=2))
    assert len(evicted) == 3
    assert service.statistics().total_items == 2


def test_operations_are_traced_via_existing_observability_service() -> None:
    obs = ObservabilityService(TraceStore())
    service = MemoryService(observability_service=obs)
    trace_id = obs.start_trace("plan-1")

    with trace_context(trace_id), agent_context("file_agent"):
        item = service.remember("Title", "Summary", MemoryType.DATASET)
        service.recall(item.memory_id)

    trace = obs.get_trace(trace_id)
    tool_names = [t.tool_name for t in trace.tool_traces]
    assert "memory.remember" in tool_names
    assert "memory.recall" in tool_names
    assert all(t.agent_name == "file_agent" for t in trace.tool_traces)


def test_operations_outside_a_trace_context_are_not_recorded() -> None:
    obs = ObservabilityService(TraceStore())
    service = MemoryService(observability_service=obs)
    obs.start_trace("plan-1")

    service.remember("Title", "Summary", MemoryType.DATASET)

    # No trace_context was ever entered, so nothing should be attributed.
    for trace in obs.list_traces():
        assert trace.tool_traces == []


def test_failed_recall_is_traced_as_failed() -> None:
    obs = ObservabilityService(TraceStore())
    service = MemoryService(observability_service=obs)
    trace_id = obs.start_trace("plan-1")

    with trace_context(trace_id), pytest.raises(MemoryItemNotFoundError):
        service.recall("does-not-exist")

    trace = obs.get_trace(trace_id)
    assert trace.tool_traces[0].status.value == "failed"
