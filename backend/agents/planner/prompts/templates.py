"""Planner prompt templates: one shared structure, seven named categories.

Every category registers the same underlying template text under its own
``PromptManager`` name — sharing the instructional boilerplate (DRY) while
keeping each category individually addressable/overridable later, and
each is rendered with a category-specific worked example
(``backend.agents.planner.examples.plan_examples``).

``select_category()`` is a deterministic keyword lookup that decides which
example/template to show the LLM — it is infrastructure for prompt
selection, not the intent understanding itself; that happens inside the
model call this selection prepares for. Order matters: more specific
categories are checked before more general ones (e.g.
``report_with_market_context`` before the plain ``report_generation``,
``sql_analysis`` before ``csv_analysis``'s generic "analyze"), since
matching is first-match-wins.
"""

from backend.ai.prompts.manager import PromptManager

_BASE_TEMPLATE = (
    "You are the Planner Agent for InsightPilot, a business intelligence assistant. You are "
    "the brain of the system: you decide which agents run, in which order, and why - you never "
    "execute anything yourself. A separate orchestration layer runs whatever plan you produce.\n"
    "\n"
    "Agents you may reference by name in a step's node_name (do not invent any other name):\n"
    "{available_services}\n"
    "\n"
    "Uploaded datasets: {datasets_summary}\n"
    "Available SQL connections: {sql_connections_summary}\n"
    "Available browser/research context: {browser_context_summary}\n"
    "Existing reports: {existing_reports_summary}\n"
    "Conversation summary so far: {conversation_summary}\n"
    "\n"
    "Respond with ONLY a single JSON object (no markdown fences, no prose before or "
    "after it) with these top-level fields: goal, reasoning_summary, confidence "
    "(0.0-1.0), warnings (list of strings), assumptions (list of strings), "
    "estimated_complexity (one of low, medium, high), estimated_duration (seconds, "
    "or null), and steps (a list of objects, each with step_id, name, description, "
    "node_name, dependencies - a list of other step_id values that must run first - "
    "and inputs - a JSON object of the raw inputs that step's agent needs).\n"
    "\n"
    "Only ever reference node_name values from the agents listed above - never invent "
    "an agent that isn't listed.\n"
    "\n"
    "Every step's description must explain WHY that agent was selected, in terms of "
    "the user's request - for example 'BrowserAgent selected because the user requested "
    "recent market information.' or 'ReportAgent selected because the user requested a "
    "report.' Do not write a generic description; ground it in this specific request.\n"
    "\n"
    "Only populate inputs for steps whose raw input is knowable right now - a dataset "
    "reference for a file-ingesting agent, a table or query for a SQL agent, or search "
    "topics for a browser agent. Steps that depend on another step's output (a report "
    "or summary agent) should leave inputs empty - the orchestration layer resolves "
    "those automatically from the prior step's result once it has actually run.\n"
    "\n"
    "Here is a worked example for a similar kind of request:\n"
    "{example_json}\n"
    "\n"
    "Now produce a plan for this request:\n"
    "{user_request}\n"
)

PROMPT_NAMES: dict[str, str] = {
    "csv_analysis": "planner.csv_analysis",
    "sql_analysis": "planner.sql_analysis",
    "report_generation": "planner.report_generation",
    "comparison_request": "planner.comparison_request",
    "report_with_market_context": "planner.report_with_market_context",
    "executive_summary_only": "planner.executive_summary_only",
    "data_cleaning_request": "planner.data_cleaning_request",
}

DEFAULT_CATEGORY = "csv_analysis"

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "data_cleaning_request": ("clean", "cleaning", "missing values", "duplicates"),
    "report_with_market_context": ("market context", "market research", "recent market", "industry context"),
    "comparison_request": ("compare", "comparison", "versus", " vs "),
    "executive_summary_only": ("executive summary", "business recommendations", "summarize the report"),
    "report_generation": ("report",),
    "sql_analysis": ("sql", "database", "table", "query"),
    "csv_analysis": ("analyze", "analyse", "analysis", "explore", "summarize", "summarise", "overview", "csv", "file"),
}


def register_planner_prompts(prompt_manager: PromptManager) -> None:
    """Register every planner prompt category. Idempotent: safe to call repeatedly."""
    for name in PROMPT_NAMES.values():
        prompt_manager.register(name, _BASE_TEMPLATE)


def select_category(user_request: str) -> str:
    """Pick a prompt category by simple keyword matching over the user's request.

    Deterministic and mechanical — not a stand-in for the LLM's own
    reasoning, just a way to decide which worked example to show it.
    """
    lowered = user_request.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return DEFAULT_CATEGORY


def prompt_name_for_category(category: str) -> str:
    """Return the registered prompt name for a category, falling back to the default."""
    return PROMPT_NAMES.get(category, PROMPT_NAMES[DEFAULT_CATEGORY])
