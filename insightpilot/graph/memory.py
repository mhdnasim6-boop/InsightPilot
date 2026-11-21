"""Context construction for the LLM: summary of old turns + recent messages, trimmed to a token budget.

The checkpointer keeps the FULL history for every thread. What is sent to the model is only
(1) a running summary of older turns and (2) the most recent messages that fit the budget.
That is what lets a 3B model with a small context window hold a long conversation.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, trim_messages

from ..config import Settings
from ..providers.base import AIProvider, message_text

SUMMARY_PROMPT = (
    "You maintain a running summary of a conversation between a business user and a data assistant. "
    "Update the summary with the new messages. Keep: which dataset is being analysed, what the user asked, "
    "the key figures and findings reported, and any decisions made. Keep it under 150 words. "
    "Do not invent anything."
)


def approx_tokens(messages: list[BaseMessage]) -> int:
    """Cheap token estimate (about 4 characters per token); fine for budgeting, no tokenizer needed."""
    return sum(len(message_text(m.content)) // 4 + 4 for m in messages)


def _plain(m: BaseMessage) -> BaseMessage | None:
    text = message_text(m.content).strip()
    if not text:
        return None
    if isinstance(m, HumanMessage):
        return HumanMessage(content=text)
    if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
        return AIMessage(content=text)
    return None


def build_context(state: dict, settings: Settings) -> list[BaseMessage]:
    """Messages to send to the LLM for this turn (the latest user question is always included)."""
    messages = state.get("messages", [])
    recent = [p for p in (_plain(m) for m in messages[state.get("summarized_upto", 0):]) if p is not None]
    trimmed = trim_messages(recent, max_tokens=settings.trim_max_tokens, strategy="last",
                            token_counter=approx_tokens, start_on="human", allow_partial=False)
    if not trimmed and recent:
        trimmed = [recent[-1]]
    out: list[BaseMessage] = []
    if state.get("conversation_summary"):
        out.append(SystemMessage(content="Summary of the earlier conversation: " + state["conversation_summary"]))
    return out + list(trimmed)


def maybe_summarize(provider: AIProvider, state: dict, settings: Settings) -> dict:
    """Fold older messages into `conversation_summary` once the unsummarised tail gets long."""
    messages = state.get("messages", [])
    upto = state.get("summarized_upto", 0)
    if len(messages) - upto <= settings.summarize_after_messages:
        return {}
    cut = len(messages) - settings.keep_recent_messages
    chunk = [p for p in (_plain(m) for m in messages[upto:cut]) if p is not None]
    if not chunk:
        return {"summarized_upto": cut}
    transcript = "\n".join(f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {message_text(m.content)[:600]}" for m in chunk)
    prev = state.get("conversation_summary", "")
    try:
        summary = provider.chat([SystemMessage(content=SUMMARY_PROMPT),
                                 HumanMessage(content=f"Current summary: {prev or '(none)'}\n\nNew messages:\n{transcript}")])
    except Exception as exc:  # noqa: BLE001 - summarising is optional; never fail the turn because of it
        return {"errors": [f"summarisation skipped: {exc}"]}
    return {"conversation_summary": summary.strip(), "summarized_upto": cut}
