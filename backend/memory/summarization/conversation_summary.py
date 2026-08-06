"""summarize_conversation(): a deterministic, extractive summary of a session's
CONVERSATION-type memories — adds a topic/count header on top of
``MemorySummarizer``'s generic combination, since a conversation summary
is specifically useful to know "how many exchanges" and "about what."
"""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.summarization.memory_summarizer import MemorySummarizer

_summarizer = MemorySummarizer()


def summarize_conversation(conversation_memories: list[MemoryItem], max_length: int = 500) -> str:
    """Summarize a session's CONVERSATION-type memories, oldest first, deterministically."""
    if not conversation_memories:
        return "No prior conversation."

    ordered = sorted(conversation_memories, key=lambda item: item.created_at)
    topic_tags = sorted({tag for item in ordered for tag in item.tags})
    topics_line = f" Topics discussed: {', '.join(topic_tags)}." if topic_tags else ""
    header = f"{len(ordered)} prior exchange(s).{topics_line}"
    body = _summarizer.summarize(ordered, max_length=max_length)
    return f"{header}\n{body}"
