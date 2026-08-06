"""Deterministic intent classification.

Mirrors ``backend.agents.planner.prompts.templates.select_category()``:
simple, ordered keyword matching, not a stand-in for the LLM's own
reasoning. Its only job is choosing which slice of already-computed
facts to retrieve and which prompt style to render — the LLM never
classifies anything itself in this phase.
"""

from enum import Enum


class Intent(str, Enum):
    """Every kind of question the assistant recognizes."""

    SUMMARY = "summary"
    KPI = "kpi"
    TREND = "trend"
    COMPARISON = "comparison"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    EXPLANATION = "explanation"
    VISUALIZATION = "visualization"
    PLANNING = "planning"
    REPORT = "report"
    WORKFLOW = "workflow"
    REFLECTION = "reflection"
    OPTIMIZATION = "optimization"
    GENERAL = "general"


DEFAULT_INTENT = Intent.GENERAL

# Order matters: the first matching intent wins, so more specific keyword
# sets are listed before broader, catch-all-ish ones (EXPLANATION last,
# before the GENERAL default, since "why"/"explain" can otherwise shadow
# a more specific question). REPORT/WORKFLOW/REFLECTION/OPTIMIZATION use
# single, fairly unambiguous nouns ("report", "workflow", "reflection",
# an "optim" prefix covering optimize/optimization/optimized), so they're
# checked before PLANNING's own broader, vaguer phrases ("how do i",
# "recommend") to avoid a workflow/optimization question being shadowed
# by a much weaker planning-keyword match.
_INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.ANOMALY: ("anomaly", "anomalies", "outlier", "outliers", "unusual", "strange value"),
    Intent.CORRELATION: ("correlation", "correlate", "correlated", "related to", "linked to"),
    Intent.TREND: ("trend", "over time", "increasing", "decreasing", "growth", "change over"),
    Intent.COMPARISON: ("compare", "comparison", "versus", " vs ", "difference between"),
    Intent.VISUALIZATION: ("chart", "graph", "plot", "visualize", "visualise", "visualization", "show me a"),
    Intent.REPORT: ("report", "executive summary", "document"),
    Intent.WORKFLOW: ("workflow", "pipeline run", "automation run"),
    Intent.REFLECTION: ("reflection", "how did it go", "how did that go", "lessons learned", "post-mortem", "postmortem"),
    Intent.OPTIMIZATION: ("optim", "adaptive planning"),
    Intent.PLANNING: ("plan", "next steps", "what should i do", "recommend", "how do i"),
    Intent.KPI: ("kpi", "metric", "how many", "total", "average", "key metric"),
    Intent.SUMMARY: ("summary", "summarize", "summarise", "overview", "tell me about", "describe this dataset"),
    Intent.EXPLANATION: ("why", "explain", "how come", "reason for", "what does this mean"),
}


class QuestionClassifier:
    """Classifies a user's question into an :class:`Intent` by keyword matching."""

    def classify(self, question: str) -> Intent:
        """Return the first matching intent, or :data:`DEFAULT_INTENT` if none match."""
        lowered = question.lower()
        for intent, keywords in _INTENT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return intent
        return DEFAULT_INTENT
