"""The LangGraph workflow: a Supervisor hub with five specialist agents and two Human-in-the-Loop approvals.

    START -> supervisor -> { data_cleaning | data_analyst | visualization | research | report_email | respond }
    data_cleaning  -> cleaning_approval (interrupt) -> supervisor
    report_email   -> email_approval   (interrupt) -> supervisor
    every other specialist returns to the supervisor;  respond -> summarize -> END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..agents.analyst import make_data_analyst
from ..agents.cleaning import make_cleaning_approval, make_data_cleaning, route_after_cleaning
from ..agents.report_email import make_email_approval, make_report_email, route_after_report
from ..agents.research import make_research
from ..agents.responder import make_respond
from ..agents.supervisor import make_supervisor, route_from_supervisor
from ..agents.visualization import make_visualization
from ..config import Settings
from ..data.store import DatasetStore
from ..providers.base import AIProvider
from .memory import maybe_summarize
from .state import AgentState

NODES = ("supervisor", "data_cleaning", "cleaning_approval", "data_analyst", "visualization",
         "research", "report_email", "email_approval", "respond", "summarize")


def build_graph(provider: AIProvider, store: DatasetStore, settings: Settings, checkpointer=None, search_fn=None):
    g = StateGraph(AgentState)
    g.add_node("supervisor", make_supervisor(provider, settings))
    g.add_node("data_cleaning", make_data_cleaning(provider, store, settings))
    g.add_node("cleaning_approval", make_cleaning_approval(store))
    g.add_node("data_analyst", make_data_analyst(provider, store, settings))
    g.add_node("visualization", make_visualization(provider))
    g.add_node("research", make_research(provider, settings, search_fn))
    g.add_node("report_email", make_report_email(provider, store, settings))
    g.add_node("email_approval", make_email_approval(settings))
    g.add_node("respond", make_respond(provider))
    g.add_node("summarize", lambda state: maybe_summarize(provider, state, settings))

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_from_supervisor, {
        "data_cleaning": "data_cleaning", "data_analyst": "data_analyst", "visualization": "visualization",
        "research": "research", "report_email": "report_email", "respond": "respond"})
    g.add_conditional_edges("data_cleaning", route_after_cleaning,
                            {"cleaning_approval": "cleaning_approval", "supervisor": "supervisor"})
    g.add_conditional_edges("report_email", route_after_report,
                            {"email_approval": "email_approval", "supervisor": "supervisor"})
    for name in ("cleaning_approval", "data_analyst", "visualization", "research", "email_approval"):
        g.add_edge(name, "supervisor")
    g.add_edge("respond", "summarize")
    g.add_edge("summarize", END)
    return g.compile(checkpointer=checkpointer)
