"""ExecutiveSummaryAgent's single prompt template.

One prompt, always — unlike the Planner's category-based selection,
there is only one kind of request here: "summarize this already-built
report." The grounding rules are the load-bearing part of this template:
the model is given the report's own rendered text (via
``MarkdownReportExporter`` — nothing recomputed) and, optionally, an
external-context block, and is explicitly forbidden from citing any
number, KPI, chart, or trend that isn't already present in that text.

The worked example embedded below serves two purposes at once, mirroring
``backend.agents.planner.prompts.templates``'s own worked-example
technique: few-shot guidance for a real provider, and — since
``MockProvider`` deterministically echoes its prompt back — a legitimate
source of parseable JSON for tests that exercise the real
prompt -> AIService -> parse pipeline with no external LLM.
"""

from backend.ai.prompts.manager import PromptManager

PROMPT_NAME = "executive_summary.generate"

WORKED_EXAMPLE_JSON = """{
  "executive_summary": "Revenue grew steadily across both regions this period, led by the East region's stronger performance. Data quality was high after cleaning, and no critical anomalies were found. No external market context was available for this summary.",
  "key_findings": [
    "East region generated the majority of total revenue.",
    "Overall data quality score was high after the cleaning pipeline ran.",
    "No significant anomalies were detected in the analyzed columns."
  ],
  "risks": [
    "West region's growth rate lagged behind East, which may indicate a regional demand issue worth investigating."
  ],
  "recommendations": [
    "Investigate the drivers behind East region's stronger performance to see if they can be replicated in West."
  ],
  "follow_up_actions": [
    "Review West region's marketing and pricing strategy for the next reporting period."
  ],
  "confidence": 0.8
}"""

_TEMPLATE = (
    "You are the Executive Summary Agent for InsightPilot, a business intelligence "
    "assistant. Your only job is to read an already-generated business report and "
    "write a concise executive summary for business leaders. You never analyze data "
    "yourself and you never invent facts.\n"
    "\n"
    "GROUNDING RULES (follow these exactly):\n"
    "- Only summarize what is written in the REPORT CONTENT and EXTERNAL CONTEXT "
    "sections below.\n"
    "- Never invent a number, KPI, chart, or trend that is not already present in "
    "that text.\n"
    "- If EXTERNAL CONTEXT says no external context was available, your "
    "executive_summary must explicitly say that no external business context was "
    "available - never imply market context you were not given.\n"
    "\n"
    "Respond with ONLY a single JSON object (no markdown fences, no prose before or "
    "after it) with these top-level fields: executive_summary (a short narrative "
    "paragraph covering major KPIs, business highlights, and external market context "
    "if any), key_findings (list of strings), risks (list of strings), "
    "recommendations (list of strings), follow_up_actions (list of strings), and "
    "confidence (0.0-1.0).\n"
    "\n"
    "Here is a worked example of the expected response shape:\n"
    "{worked_example_json}\n"
    "\n"
    "REPORT CONTENT:\n"
    "{report_content}\n"
    "\n"
    "EXTERNAL CONTEXT:\n"
    "{external_context}\n"
    "\n"
    "Now write the executive summary for the report above.\n"
)


def register_executive_summary_prompts(prompt_manager: PromptManager) -> None:
    """Register the executive summary prompt. Idempotent: safe to call repeatedly."""
    prompt_manager.register(PROMPT_NAME, _TEMPLATE)
