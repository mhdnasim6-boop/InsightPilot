"""Tests for deterministic, extractive memory summarization — no AI calls."""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.summarization.conversation_summary import summarize_conversation
from backend.memory.summarization.memory_summarizer import MemorySummarizer
from backend.utils.time import utc_now


def _item(memory_id: str, title: str, summary: str, tags: list[str] | None = None) -> MemoryItem:
    now = utc_now()
    return MemoryItem(
        memory_id=memory_id,
        title=title,
        summary=summary,
        memory_type=MemoryType.CONVERSATION,
        scope=MemoryScope.SESSION,
        created_at=now,
        updated_at=now,
        tags=tags or [],
    )


def test_summarizer_returns_placeholder_for_no_items() -> None:
    assert MemorySummarizer().summarize([]) == "No memories to summarize."


def test_summarizer_joins_title_and_summary_per_item() -> None:
    items = [_item("m1", "First", "First summary"), _item("m2", "Second", "Second summary")]
    result = MemorySummarizer().summarize(items)
    assert "- First: First summary" in result
    assert "- Second: Second summary" in result


def test_summarizer_orders_oldest_first_regardless_of_input_order() -> None:
    import time

    first = _item("m1", "First", "s1")
    time.sleep(0.01)
    second = _item("m2", "Second", "s2")

    result = MemorySummarizer().summarize([second, first])
    assert result.index("First") < result.index("Second")


def test_summarizer_truncates_to_max_length() -> None:
    items = [_item("m1", "Title", "x" * 1000)]
    result = MemorySummarizer().summarize(items, max_length=50)
    assert len(result) <= 50
    assert result.endswith("…")


def test_summarize_conversation_with_no_memories() -> None:
    assert summarize_conversation([]) == "No prior conversation."


def test_summarize_conversation_includes_count_and_topics() -> None:
    items = [
        _item("m1", "Chat: what are the KPIs?", "You have 3 KPIs.", tags=["kpi"]),
        _item("m2", "Chat: any anomalies?", "One anomaly found.", tags=["anomaly"]),
    ]
    result = summarize_conversation(items)
    assert "2 prior exchange(s)" in result
    assert "anomaly" in result
    assert "kpi" in result
