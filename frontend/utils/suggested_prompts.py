"""Dynamic suggested Chat prompts — generated from whatever the dashboard's own
session state currently holds, instead of a fixed, generic list.

Pure formatting over already-fetched dicts, mirroring
``frontend.utils.chat_context``'s own "never derive a new fact, only pick
and phrase one that's already there" discipline — every suggestion here
names a real KPI/report/workflow already present in state, never a
fabricated one. Falls back to the original generic starters when nothing
more specific is available yet — a fresh session with no data behaves
exactly like it did before this module existed.
"""

from frontend.state.session_state import DashboardState

GENERIC_STARTERS = [
    "Give me a summary of this dataset.",
    "What are the key KPIs?",
    "Are there any anomalies?",
]

_MAX_SUGGESTIONS = 4


def generate_starter_prompts(state: DashboardState) -> list[str]:
    """Return up to 4 suggested opening questions, tailored to whatever the user
    has already done in this session."""
    suggestions: list[str] = []

    analysis = state.current_analysis
    if analysis:
        kpis = analysis.get("kpis") or []
        if kpis:
            top_kpi_name = kpis[0].get("name")
            if top_kpi_name:
                suggestions.append(f"What's driving {top_kpi_name}?")
        anomalies = analysis.get("anomalies") or {}
        if anomalies.get("applicable") and anomalies.get("columns"):
            suggestions.append("Explain the anomalies you found.")

    if state.current_visualization:
        suggestions.append("Which chart tells the most important story?")

    if state.current_report:
        suggestions.append("Summarize this report.")

    if state.current_workflow:
        workflow_name = ((state.current_workflow or {}).get("definition") or {}).get("name")
        suggestions.append(
            f"What's the status of the '{workflow_name}' workflow?" if workflow_name else "What's the status of this workflow?"
        )

    if state.current_reflection:
        suggestions.append("What's the reflection on this execution?")

    if state.current_optimization:
        suggestions.append("What did the optimizer suggest?")

    if not suggestions:
        return list(GENERIC_STARTERS)

    # Keep one dataset-level generic starter in the mix, then fill the rest
    # with the most specific signals available, de-duplicated in order.
    ordered = [GENERIC_STARTERS[0], *suggestions]
    seen: set[str] = set()
    deduped: list[str] = []
    for prompt in ordered:
        if prompt not in seen:
            seen.add(prompt)
            deduped.append(prompt)
    return deduped[:_MAX_SUGGESTIONS]
