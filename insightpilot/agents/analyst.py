"""Data Analyst Agent: a bounded tool loop where the LLM writes SQL and DuckDB does all the arithmetic.

Inner graph:  llm -> (tool calls?) -> tools -> record -> llm ...   ends when the model stops calling tools,
or after `max_sql_retries` failed queries. Tool messages stay inside this inner graph; only the validated
result table and a short note are written to the shared state.
"""
from __future__ import annotations

import json
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from ..config import Settings
from ..data.store import DatasetStore
from ..graph.memory import build_context
from ..providers.base import AIProvider, message_text
from ..tools.sql_tool import make_sql_tools
from .common import audit, latest_user_question, ran

ANALYST_PROMPT = """You are the Data Analyst agent. Answer the user's question by querying a DuckDB table named `data`.
{brief}

Rules:
- Use the run_sql tool with ONE read-only SELECT query. You may call get_schema first if unsure.
- Do all calculations in SQL (SUM, AVG, COUNT, GROUP BY, ORDER BY). Never calculate numbers yourself.
- For month-level analysis use strftime(CAST(col AS DATE), '%Y-%m') or date_trunc('month', ...).
- Return only the columns needed, with clear names (e.g. total_revenue), sorted sensibly, and LIMIT 50 unless the user wants more.
- For "why did X drop" questions, MEASURE the change: compare periods and break down by region/category to find where it happened.
- If run_sql returns an error, read it, fix the query and try again.
- When you have a good result, reply with ONE short sentence describing what the result shows. Do not repeat the numbers."""


class AnalystState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    result: dict
    failures: int
    last_error: str


def _record(state: AnalystState) -> dict:
    """Capture the latest run_sql outcome from the tool messages added in the last step."""
    result, failures, last_error = state.get("result"), state.get("failures", 0), state.get("last_error", "")
    for m in reversed(state["messages"]):
        if not isinstance(m, ToolMessage):
            break
        if m.name != "run_sql":
            continue
        try:
            payload = json.loads(message_text(m.content))
        except ValueError:
            payload = {"ok": False, "error": "unreadable tool output"}
        if payload.get("ok"):
            result = {k: payload[k] for k in ("sql", "columns", "rows", "row_count", "truncated")}
        else:
            failures += 1
            last_error = str(payload.get("error", ""))
    return {"result": result, "failures": failures, "last_error": last_error}


def build_analyst_graph(provider: AIProvider, tools: list, settings: Settings, brief: str):
    model = provider.get_chat_model().bind_tools(tools)

    def llm(state: AnalystState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    def after_record(state: AnalystState) -> str:
        return END if state.get("failures", 0) >= settings.max_sql_retries else "llm"

    g = StateGraph(AnalystState)
    g.add_node("llm", llm)
    g.add_node("tools", ToolNode(tools))
    g.add_node("record", _record)
    g.add_edge(START, "llm")
    g.add_conditional_edges("llm", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "record")
    g.add_conditional_edges("record", after_record, {"llm": "llm", END: END})
    return g.compile()


def make_data_analyst(provider: AIProvider, store: DatasetStore, settings: Settings):
    def data_analyst(state: dict) -> dict:
        dataset_id = state["dataset_id"]
        tools = make_sql_tools(store, dataset_id)
        inner = build_analyst_graph(provider, tools, settings, state.get("dataset_brief", ""))
        brief = state.get("dataset_brief") or ""
        msgs = [SystemMessage(content=ANALYST_PROMPT.format(brief=brief))] + build_context(state, settings)
        update: dict = {"agents_run": ran(state, "data_analyst")}
        try:
            out = inner.invoke({"messages": msgs, "failures": 0},
                               config={"recursion_limit": 4 * (settings.max_sql_retries + 3)})
        except Exception as exc:  # noqa: BLE001 - includes inner recursion limit; connection errors re-raise below
            from ..providers.base import ProviderUnavailable, is_connection_error
            if is_connection_error(exc):
                raise ProviderUnavailable(f"{provider.name}: {exc}") from exc
            update["errors"] = [f"analyst failed: {exc}"]
            update["audit"] = [audit("data_analyst", "failed", str(exc))]
            update["analyst_note"] = "I couldn't complete the analysis for that question."
            return update
        result = out.get("result")
        last = out["messages"][-1] if out.get("messages") else None
        note = message_text(last.content).strip() if isinstance(last, AIMessage) else ""
        if result:
            update.update(analysis_result={**result, "question": latest_user_question(state)},
                          analyst_note=note,
                          audit=[audit("data_analyst", "ok", f"{result['row_count']} rows")])
        else:
            update.update(analyst_note="I couldn't get a valid result for that question. Try rephrasing it, or ask about specific columns.",
                          errors=[f"analyst: no valid result ({out.get('last_error', '')})"],
                          audit=[audit("data_analyst", "failed", out.get("last_error", "no result"))])
        return update

    return data_analyst
