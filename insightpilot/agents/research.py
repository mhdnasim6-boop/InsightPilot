"""Research Agent: an existing, prebuilt ReAct agent (LangChain `create_agent`) given one external tool, web search.

We do not write its reasoning loop; we configure it (prompt + tool + cycle limit) and wrap its output.
Search results are kept as structured evidence with sources and are always labelled as possible context, not proof.
"""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ..config import Settings
from ..providers.base import AIProvider, ProviderUnavailable, is_connection_error, message_text
from ..tools.search_tool import make_search_tool
from .common import audit, latest_user_question, ran

try:  # create_react_agent is deprecated in recent LangGraph releases
    from langchain.agents import create_agent as _create_agent

    def _build_agent(model, tools, prompt):
        return _create_agent(model, tools, system_prompt=prompt)
except ImportError:  # pragma: no cover - older installs
    from langgraph.prebuilt import create_react_agent as _create_react_agent

    def _build_agent(model, tools, prompt):
        return _create_react_agent(model, tools, prompt=prompt)

RESEARCH_PROMPT = """You are the Research agent. A data analysis found a business change; find possible EXTERNAL context
(news, market events, supply or regulatory changes) that may relate to it.
Use the web_search tool with specific queries (industry, region, time period). Search at most {n} times.
Then reply with 2-3 sentences summarising what you found. Say 'may be related' - never claim a cause.
If nothing relevant was found, say so plainly."""


def _brief(state: dict) -> str:
    res = state.get("analysis_result") or {}
    return (f"User question: {latest_user_question(state)}\nDataset: {state.get('dataset_brief', '')}\n"
            f"Analysis columns: {res.get('columns')}\nAnalysis rows (first 8): {res.get('rows', [])[:8]}")


def make_research(provider: AIProvider, settings: Settings, search_fn=None):
    def research(state: dict) -> dict:
        update: dict = {"agents_run": ran(state, "research")}
        if search_fn is None and not settings.tavily_api_key:
            update.update(research_note="Web search is not configured (set TAVILY_API_KEY), so no external context was gathered.",
                          external_evidence=[], audit=[audit("research", "skipped", "no TAVILY_API_KEY")])
            return update
        tool = make_search_tool(settings, search_fn)
        agent = _build_agent(provider.get_chat_model(), [tool], RESEARCH_PROMPT.format(n=settings.max_research_cycles))
        try:
            out = agent.invoke({"messages": [HumanMessage(content=_brief(state))]},
                               config={"recursion_limit": 2 * settings.max_research_cycles + 3})
        except Exception as exc:  # noqa: BLE001
            if is_connection_error(exc):
                raise ProviderUnavailable(f"{provider.name}: {exc}") from exc
            update.update(research_note="The web research step failed, so no external context is included.",
                          errors=[f"research failed: {exc}"], audit=[audit("research", "failed", str(exc))])
            return update
        evidence, seen = [], set()
        for m in out["messages"]:
            if isinstance(m, ToolMessage):
                try:
                    payload = json.loads(message_text(m.content))
                except ValueError:
                    continue
                for r in payload.get("results", []):
                    if r.get("url") and r["url"] not in seen:
                        seen.add(r["url"])
                        evidence.append(r)
        last = out["messages"][-1]
        note = message_text(last.content).strip() if isinstance(last, AIMessage) else ""
        update.update(external_evidence=evidence[:8], research_note=note,
                      audit=[audit("research", "ok", f"{len(evidence)} sources")])
        return update

    return research
