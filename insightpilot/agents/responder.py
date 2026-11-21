"""Final response node: turns verified results into the answer the user reads and records it in memory."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..providers.base import AIProvider, ProviderUnavailable
from .common import latest_user_question

RESPOND_PROMPT = """You write the final answer for a business user. Use ONLY the verified results provided.
Lead with the direct answer in 1-3 sentences, then at most 3 short supporting points. Copy numbers exactly as they
appear in the table; do not compute new numbers. If external context is provided, say it 'may be related' and never
that it caused the change. No headings. Plain business language."""


def _fmt(v) -> str:
    return f"{v:,.2f}" if isinstance(v, float) else str(v)


def _table(res: dict, n: int = 8) -> str:
    cols, rows = res.get("columns", []), res.get("rows", [])[:n]
    lines = [" | ".join(cols)] + [" | ".join(_fmt(v) for v in r) for r in rows]
    if res.get("row_count", 0) > n:
        lines.append(f"... ({res['row_count']} rows in total)")
    return "\n".join(lines)


def _footer(state: dict) -> str:
    parts = []
    if state.get("visualization"):
        parts.append("A chart is shown below.")
    if state.get("report"):
        parts.append("The PDF report is ready to download.")
    ev = state.get("external_evidence") or []
    if ev:
        parts.append("Possible external context (may be related, not proof):\n" + "\n".join(
            f"- [{e.get('title', e['url'])}]({e['url']}) ({e.get('publisher', '')})" for e in ev[:4]))
    status = state.get("email_status")
    if status:
        parts.append({"sent": "Email sent.", "saved_to_outbox": "No mail server is configured, so the email was saved to the outbox instead of being sent.",
                      "rejected": "Email not sent (you declined).", "failed": "The email could not be sent: " + state.get("email_detail", ""),
                      "needs_recipient": state.get("email_detail", "")}.get(status, ""))
    return "\n\n".join(p for p in parts if p)


def make_respond(provider: AIProvider):
    def respond(state: dict) -> dict:
        if state.get("task") == "clean_dataset":
            log = state.get("cleaning_log", [])
            text = "Cleaning finished. " + " ".join(x.get("message", "") for x in log) if log else "Cleaning finished."
            return {"final_answer": text, "messages": [AIMessage(content=text)]}
        text = state.get("final_answer", "")
        res = state.get("analysis_result")
        if not text:
            if res:
                try:
                    text = provider.chat([SystemMessage(content=RESPOND_PROMPT), HumanMessage(content=(
                        f"Question: {latest_user_question(state)}\nVerified result table:\n{_table(res)}\n"
                        f"Analyst note: {state.get('analyst_note', '')}\nExternal context: {state.get('research_note', '') or 'none'}"))]).strip()
                except ProviderUnavailable:
                    raise
                except Exception:  # noqa: BLE001 - fall back to the verified table
                    text = ""
                if not text:
                    text = "Here is what the data shows:\n\n" + _table(res)
            else:
                text = state.get("analyst_note") or "I couldn't find an answer to that. Could you rephrase the question?"
        foot = _footer(state)
        full = text + ("\n\n" + foot if foot else "")
        return {"final_answer": full, "messages": [AIMessage(content=full)]}

    return respond
