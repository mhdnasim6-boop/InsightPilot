"""MemoryService: the only public entry point for the memory layer.

``remember()``/``recall()``/``forget()``/``search()``/``summarize()``/
``statistics()``/``export()`` — nothing outside ``backend/memory/``
should import ``MemoryStore`` directly; every integration (Chat,
Planner, File/SQL/Browser/Report/ExecutiveSummary agents, Approval,
Execution) goes through this class alone.

Every operation is recorded as a ``ToolTrace`` via the *existing*
``ObservabilityService.record_tool_trace()`` — the exact same call
``TracingTool`` already makes for every real tool call — tagged with
whichever trace/agent context is currently active via
``backend.observability.context``. No new tracing model or mechanism is
introduced, per this phase's own "reuse the existing observability
system" mandate: a memory operation performed outside any active trace
(``current_trace_id`` unset) simply isn't recorded anywhere, exactly
like ``TracingTool``'s own no-op-outside-a-trace-context behavior.
"""

import time
from datetime import datetime
from typing import Any, Literal

from backend.memory.exceptions import MemoryItemNotFoundError
from backend.memory.exporters.json_exporter import JSONMemoryExporter
from backend.memory.exporters.markdown_exporter import MarkdownMemoryExporter
from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_result import MemoryResult
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.memory.models.memory_type import MemoryType
from backend.memory.models.retention_policy import RetentionPolicy
from backend.memory.retention.cleanup import run_cleanup
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.services.statistics_service import StatisticsService
from backend.memory.store.memory_store import MemoryStore
from backend.memory.summarization.conversation_summary import summarize_conversation
from backend.memory.summarization.memory_summarizer import (
    DEFAULT_MAX_LENGTH,
    MemorySummarizer,
)
from backend.observability.context import current_agent_name
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class MemoryService:
    """Remembers, recalls, searches, summarizes, and manages generic knowledge."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        retrieval_engine: RetrievalEngine | None = None,
        summarizer: MemorySummarizer | None = None,
        json_exporter: JSONMemoryExporter | None = None,
        markdown_exporter: MarkdownMemoryExporter | None = None,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._store = store or MemoryStore()
        self._retrieval_engine = retrieval_engine or RetrievalEngine()
        self._summarizer = summarizer or MemorySummarizer()
        self._json_exporter = json_exporter or JSONMemoryExporter()
        self._markdown_exporter = markdown_exporter or MarkdownMemoryExporter()
        self._observability_service = observability_service
        self._statistics_service = StatisticsService(self._store)

    def remember(
        self,
        title: str,
        summary: str,
        memory_type: MemoryType,
        scope: MemoryScope = MemoryScope.SESSION,
        content: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
        references: list[MemoryReference] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Store a new memory. The only way anything creates a MemoryItem."""
        start_time, start = utc_now(), time.perf_counter()
        now = utc_now()
        item = MemoryItem(
            memory_id=generate_id(),
            title=title,
            summary=summary,
            content=content or {},
            memory_type=memory_type,
            scope=scope,
            created_at=now,
            updated_at=now,
            tags=tags or [],
            importance=importance,
            references=references or [],
            metadata=metadata or {},
        )
        self._store.add(item)
        self._trace("memory.remember", start_time, start, ExecutionStatus.COMPLETED)
        return item

    def recall(self, memory_id: str) -> MemoryItem:
        """Fetch one memory by id. Raises MemoryItemNotFoundError if unknown."""
        start_time, start = utc_now(), time.perf_counter()
        item = self._store.get(memory_id)
        if item is None:
            self._trace("memory.recall", start_time, start, ExecutionStatus.FAILED, error=f"not found: {memory_id}")
            raise MemoryItemNotFoundError(f"No memory found for '{memory_id}'.")
        self._trace("memory.recall", start_time, start, ExecutionStatus.COMPLETED)
        return item

    def forget(self, memory_id: str) -> bool:
        """Delete one memory by id. Returns whether one was actually removed."""
        start_time, start = utc_now(), time.perf_counter()
        deleted = self._store.delete(memory_id)
        status = ExecutionStatus.COMPLETED if deleted else ExecutionStatus.FAILED
        self._trace("memory.forget", start_time, start, status)
        return deleted

    def search(self, query: MemoryQuery) -> MemoryResult:
        """Deterministically filter, rank, and top-k the stored memories against ``query``."""
        start_time, start = utc_now(), time.perf_counter()
        result = self._retrieval_engine.retrieve(self._store.list_all(), query)
        self._trace("memory.search", start_time, start, ExecutionStatus.COMPLETED)
        return result

    def list_all(self) -> list[MemoryItem]:
        """Return every stored memory, most recently added first."""
        return self._store.list_all()

    def summarize(self, query: MemoryQuery | None = None, max_length: int = DEFAULT_MAX_LENGTH) -> str:
        """Deterministically, extractively summarize the memories matching ``query`` (or all of them)."""
        start_time, start = utc_now(), time.perf_counter()
        items = self._retrieval_engine.retrieve(self._store.list_all(), query).items if query else self.list_all()

        if query is not None and query.memory_type == MemoryType.CONVERSATION:
            summary = summarize_conversation(items, max_length=max_length)
        else:
            summary = self._summarizer.summarize(items, max_length=max_length)

        self._trace("memory.summarize", start_time, start, ExecutionStatus.COMPLETED)
        return summary

    def statistics(self) -> MemoryStatistics:
        """Aggregate counts, recency, and average importance over every stored memory."""
        return self._statistics_service.compute()

    def export(self, export_format: Literal["json", "markdown"]) -> str:
        """Export every stored memory as JSON or Markdown."""
        items = self.list_all()
        if export_format == "json":
            return self._json_exporter.export(items)
        return self._markdown_exporter.export(items)

    def clear(self) -> None:
        """Remove every stored memory."""
        self._store.clear()

    def apply_retention(self, policy: RetentionPolicy) -> list[str]:
        """Evict whatever ``policy`` says should go. Returns the evicted memory_ids."""
        return run_cleanup(self._store, policy)

    def _trace(
        self,
        operation_name: str,
        start_time: datetime,
        start: float,
        status: ExecutionStatus,
        error: str | None = None,
    ) -> None:
        if self._observability_service is None:
            return
        self._observability_service.record_tool_trace(
            ToolTrace(
                tool_name=operation_name,
                agent_name=current_agent_name.get(),
                start_time=start_time,
                end_time=utc_now(),
                duration_ms=(time.perf_counter() - start) * 1000,
                status=status,
                error=error,
            )
        )
