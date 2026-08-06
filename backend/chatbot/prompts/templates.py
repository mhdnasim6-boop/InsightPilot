"""Chatbot prompt templates: one shared structure, one named category per intent.

Mirrors ``backend.agents.planner.prompts.templates``: every intent
registers the same underlying template text under its own
``PromptManager`` name (DRY, while keeping each category individually
addressable/overridable later). The only thing that varies today is
``style_instruction`` — how the model should frame its answer over the
facts it's given.
"""

from backend.ai.prompts.manager import PromptManager
from backend.chatbot.context.models import ChatMessage
from backend.chatbot.retrieval.classifier import Intent
from backend.ingestion.models.dataset import BusinessDataset

_BASE_TEMPLATE = (
    "You are InsightPilot's conversational business intelligence assistant.\n"
    "Answer the user's question using ONLY the facts provided below - never invent "
    "a number, chart, trend, or correlation that isn't explicitly present here. If "
    "the facts don't contain enough to answer, say so plainly instead of guessing.\n"
    "\n"
    "Dataset: {dataset_summary}\n"
    "\n"
    "Relevant facts:\n"
    "{facts}\n"
    "\n"
    "Conversation so far:\n"
    "{conversation_history}\n"
    "\n"
    "{style_instruction}\n"
    "\n"
    "User question: {question}\n"
)

PROMPT_NAMES: dict[Intent, str] = {
    Intent.SUMMARY: "chat.summary",
    Intent.KPI: "chat.kpi",
    Intent.TREND: "chat.trend",
    Intent.COMPARISON: "chat.comparison",
    Intent.ANOMALY: "chat.anomaly",
    Intent.CORRELATION: "chat.correlation",
    Intent.EXPLANATION: "chat.explanation",
    Intent.VISUALIZATION: "chat.visualization",
    Intent.PLANNING: "chat.planning",
    Intent.REPORT: "chat.report",
    Intent.WORKFLOW: "chat.workflow",
    Intent.REFLECTION: "chat.reflection",
    Intent.OPTIMIZATION: "chat.optimization",
    Intent.GENERAL: "chat.general",
}

_STYLE_INSTRUCTIONS: dict[Intent, str] = {
    Intent.SUMMARY: "Provide a concise executive summary of the dataset's key characteristics and findings.",
    Intent.KPI: "Report the specific KPI values requested, stating exact numbers from the facts above.",
    Intent.TREND: (
        "Explain the trend shown in the facts above in plain business language, noting direction and rate of change."
    ),
    Intent.COMPARISON: "Compare the relevant metrics or columns from the facts above, highlighting differences.",
    Intent.ANOMALY: "Explain the anomalies found in the facts above: which values are unusual, and why.",
    Intent.CORRELATION: "Explain the relationship(s) between columns shown in the facts above, in plain language.",
    Intent.EXPLANATION: "Explain the requested finding from the facts above, focusing on why, not just the numbers.",
    Intent.VISUALIZATION: "Describe the relevant chart(s) from the facts above: what they show and why.",
    Intent.PLANNING: "Explain the execution plan from the facts above: its goal, status, and steps.",
    Intent.REPORT: "Summarize the report from the facts above: its title, sections, and what it covers.",
    Intent.WORKFLOW: "Explain the workflow from the facts above: its purpose, current status, and steps.",
    Intent.REFLECTION: (
        "Summarize how the execution went, using the scores, strengths, weaknesses, and recommendations above."
    ),
    Intent.OPTIMIZATION: "Explain what the adaptive planner suggested and why, using the decisions above.",
    Intent.GENERAL: "Answer the user's question using the facts above as best you can.",
}


def register_chat_prompts(prompt_manager: PromptManager) -> None:
    """Register every chat prompt category. Idempotent: safe to call repeatedly."""
    for name in PROMPT_NAMES.values():
        prompt_manager.register(name, _BASE_TEMPLATE)


def prompt_name_for_intent(intent: Intent) -> str:
    """Return the registered prompt name for an intent, falling back to General."""
    return PROMPT_NAMES.get(intent, PROMPT_NAMES[Intent.GENERAL])


def style_instruction_for_intent(intent: Intent) -> str:
    """Return the style instruction that frames how the model should answer."""
    return _STYLE_INSTRUCTIONS.get(intent, _STYLE_INSTRUCTIONS[Intent.GENERAL])


def summarize_dataset(dataset: BusinessDataset | None) -> str:
    """One-line dataset identity header shown at the top of every prompt."""
    if dataset is None:
        return "No dataset selected."
    return f"{dataset.dataset_name} ({dataset.row_count} rows, {dataset.column_count} columns)"


def render_conversation_history(history: list[ChatMessage], limit: int = 6) -> str:
    """Render the most recent ``limit`` turns as ``Role: content`` lines."""
    if not history:
        return "None yet - this is the first question."
    recent = history[-limit:]
    return "\n".join(f"{message.role.capitalize()}: {message.content}" for message in recent)
