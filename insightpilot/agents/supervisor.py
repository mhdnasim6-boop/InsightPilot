"""Supervisor Agent: an LLM that decides which specialist runs next, or FINISH.

LLM decides, code enforces: the decision is a validated Pydantic object restricted to fixed agent
names, obvious rules are applied in code before the LLM is asked, and every loop is bounded.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import Settings
from ..graph.memory import build_context
from ..providers.base import AIProvider, StructuredOutputError, message_text
from ..schemas import RoutingDecision
from .common import audit, latest_user_question

SUPERVISOR_PROMPT = """You are the Supervisor of InsightPilot, a business-intelligence assistant.
You never answer data questions yourself and you never see the raw data. Each time you are called,
choose the ONE specialist that should work next, or FINISH.

Specialists:
- data_analyst: writes and runs SQL on the dataset to answer any question about the numbers
  (totals, comparisons, trends, rankings, "why did X drop" needs its measurements first).
- visualization: draws a chart of the data_analyst result. Use it after data_analyst when the result
  has several rows (a trend over time or a comparison). Skip it for a single number.
- research: searches the web for news that may explain a change. Use it ONLY when the user asks WHY
  something happened or asks for outside / market / news context, and only after data_analyst has run.
- report_email: writes a PDF report and, if requested, drafts an email. Use it ONLY when the user asks
  for a report, a written summary document, or to email something. It needs analysis results to exist.

Rules:
- Choose FINISH as soon as the user's request is fully answered. Do not run a specialist twice.
- If the user only greets you, thanks you, or asks something that needs no data, choose FINISH and put
  a short helpful answer in direct_reply.
- Never choose data_cleaning; it is handled automatically.
Reply with next_agent, a one-sentence reason, and direct_reply only when relevant."""


def _results_summary(state: dict) -> str:
    ar = state.get("analysis_result") or {}
    return (f"analysis={'yes (' + str(ar.get('row_count', 0)) + ' rows)' if ar else 'no'}; "
            f"chart={'yes' if state.get('visualization') else 'no'}; "
            f"external_evidence={len(state.get('external_evidence') or [])}; "
            f"report={'yes' if state.get('report') else 'no'}")


def _transcript(state: dict, settings: Settings) -> str:
    ctx = build_context(state, settings)[:-1]       # everything before the current question
    lines = []
    for m in ctx[-6:]:
        who = "User" if isinstance(m, HumanMessage) else "Assistant" if m.type == "ai" else "Context"
        lines.append(f"{who}: {message_text(m.content)[:300]}")
    return "\n".join(lines) or "(none)"


def _guard(state: dict, settings: Settings) -> RoutingDecision | None:
    """Rules that are always true: decided in code, with no LLM call."""
    run = state.get("agents_run", [])
    if not state.get("dataset_id"):
        return RoutingDecision(next_agent="FINISH", reason="no dataset loaded",
                               direct_reply="Please upload a dataset on the Data page first, then ask me questions about it.")
    if state.get("step_count", 0) >= settings.max_supervisor_steps:
        return RoutingDecision(next_agent="FINISH", reason="step limit reached")
    if not state.get("dataset_cleaned") and "data_cleaning" not in run:
        return RoutingDecision(next_agent="data_cleaning", reason="new dataset must be checked first")
    if state.get("task") == "clean_dataset":
        return RoutingDecision(next_agent="FINISH", reason="cleaning run complete")
    if state.get("email_status"):
        return RoutingDecision(next_agent="FINISH", reason="email step finished")
    return None


def _enforce(decision: RoutingDecision, state: dict) -> RoutingDecision:
    """Fix choices the workflow cannot honour (wrong order, repeats)."""
    run = state.get("agents_run", [])
    has_result = bool(state.get("analysis_result"))
    nxt = decision.next_agent
    if nxt == "data_cleaning":
        return RoutingDecision(next_agent="FINISH", reason="cleaning is automatic")
    if nxt != "FINISH" and nxt in run:
        return RoutingDecision(next_agent="FINISH", reason=f"{nxt} already ran this turn")
    if nxt in ("visualization", "research", "report_email") and not has_result:
        if "data_analyst" in run:
            return RoutingDecision(next_agent="FINISH", reason="no analysis result to work with")
        return RoutingDecision(next_agent="data_analyst", reason=f"{nxt} needs analysis results first")
    if nxt == "FINISH" and not run and not decision.direct_reply:
        return RoutingDecision(next_agent="FINISH", reason=decision.reason,
                               direct_reply="I'm not sure what you'd like me to analyse. Could you rephrase your question?")
    return decision


def make_supervisor(provider: AIProvider, settings: Settings):
    def supervisor(state: dict) -> dict:
        update: dict = {"step_count": state.get("step_count", 0) + 1}
        decision = _guard(state, settings)
        source = "rule"
        if decision is None:
            source = "llm"
            user_block = (
                f"Question: {latest_user_question(state)}\n"
                f"Dataset: {state.get('dataset_brief', 'unknown')}\n"
                f"Specialists already run this turn: {', '.join(state.get('agents_run', [])) or 'none'}\n"
                f"Available results: {_results_summary(state)}\n"
                f"Earlier conversation:\n{_transcript(state, settings)}"
            )
            try:
                decision = provider.structured([SystemMessage(content=SUPERVISOR_PROMPT), HumanMessage(content=user_block)],
                                               RoutingDecision)
                decision = _enforce(decision, state)
            except StructuredOutputError as exc:
                decision = RoutingDecision(next_agent="FINISH", reason="could not decide",
                                           direct_reply="I wasn't able to work out how to handle that request. Could you rephrase it?")
                update["errors"] = [str(exc)]
        update.update(next_agent=decision.next_agent, routing_reason=decision.reason)
        if decision.next_agent == "FINISH" and decision.direct_reply:
            update["final_answer"] = decision.direct_reply
        update["audit"] = [audit("supervisor", "ok", f"{source}: {decision.next_agent} - {decision.reason}")]
        return update

    return supervisor


def route_from_supervisor(state: dict) -> str:
    nxt = state.get("next_agent", "FINISH")
    return "respond" if nxt in ("FINISH", "", None) else nxt
