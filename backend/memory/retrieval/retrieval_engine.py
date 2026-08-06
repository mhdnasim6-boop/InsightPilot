"""RetrievalEngine: deterministic filtering + ranking + top-k over a list of
MemoryItems. Every signal is a plain, inspectable function of structured
fields — no embeddings, no vector search.

Ranking combines (in order of precedence): exact keyword/tag match
strength, then importance, then recency — always the same, reproducible
order for the same inputs and the same store contents.
"""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_result import MemoryResult
from backend.memory.retrieval.keyword_search import keyword_match_count, keyword_matches
from backend.memory.retrieval.tag_search import matches_any_tag, tag_match_count


class RetrievalEngine:
    """Filters, ranks, and top-k-truncates MemoryItems against a MemoryQuery."""

    def retrieve(self, items: list[MemoryItem], query: MemoryQuery) -> MemoryResult:
        """Return the items matching ``query``, ranked and truncated to ``query.top_k``."""
        filtered = [item for item in items if self._matches(item, query)]
        ranked = sorted(filtered, key=lambda item: self._rank_key(item, query), reverse=True)
        total_matched = len(ranked)
        limited = ranked[: query.top_k] if query.top_k is not None else ranked
        return MemoryResult(items=limited, total_matched=total_matched, query=query)

    def _matches(self, item: MemoryItem, query: MemoryQuery) -> bool:
        if query.memory_type is not None and item.memory_type != query.memory_type:
            return False
        if query.scope is not None and item.scope != query.scope:
            return False
        if query.session_id is not None and item.metadata.get("session_id") != query.session_id:
            return False
        if query.user_id is not None and item.metadata.get("user_id") != query.user_id:
            return False
        if query.date_from is not None and item.created_at < query.date_from:
            return False
        if query.date_to is not None and item.created_at > query.date_to:
            return False
        if query.min_importance is not None and item.importance < query.min_importance:
            return False
        if query.keyword and not keyword_matches(item, query.keyword):
            return False
        return not query.tags or matches_any_tag(item, query.tags)

    def _rank_key(self, item: MemoryItem, query: MemoryQuery) -> tuple[float, float, float]:
        keyword_score = keyword_match_count(item, query.keyword) if query.keyword else 0
        tag_score = tag_match_count(item, query.tags) if query.tags else 0
        recency = item.created_at.timestamp() if query.recent_first else 0.0
        return (float(keyword_score + tag_score), item.importance, recency)
