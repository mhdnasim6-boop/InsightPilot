"""Assembles the default graph: Planner -> Approval -> FileAgent -> Approval -> SQLAgent
-> Approval -> BrowserAgent -> Approval -> ReportAgent -> Approval -> ExecutiveSummaryAgent -> End.

Same linear shape the graph has always had (entry -> ... -> end); each
phase adds one more real node between the last one and ``EndNode``.
``EndNode`` remains the exact placeholder from ``nodes/placeholders.py``.
Every step currently triggers one full run of whichever graph is wired
(``OrchestrationService`` doesn't yet dispatch a step to its own specific
node — see ``PlanExecutor``), so a step meant only for ``FileAgent``
still passes through every other node too; each already reads only what
it needs and reports a non-crashing result when it's absent — FAILED for
File/SQL/Report/ExecutiveSummaryAgent, SKIPPED for BrowserAgent (a step
with nothing to search for isn't a failure). ReportAgentNode and
ExecutiveSummaryAgentNode both have a genuine data *dependency* on other
nodes' output (reading File/SQL/Browser/ReportAgentNode's already-written
``state.artifacts``, not just their own ``state.variables``) — see their
own modules for why. Future real graphs are assembled the same way, via
``GraphBuilder``.

``PlannerAgentNode`` is constructed by the caller (see
``backend.dependencies.orchestration.get_graph_builder``) and passed in
already wired to a ``PlannerAgentService`` — that service holds a
reference to this same ``builder``, and calls ``builder.export()`` at
plan-generation time (not construction time), so by the time any request
reaches it every node added below is already visible for dynamic agent
discovery. No circular dependency: ``GraphBuilder`` is a plain mutable
object, not the compiled ``OrchestrationService``.

Since Phase 23 (Human-in-the-Loop), one ``ApprovalNode`` (see
``backend.orchestration.nodes.approval_node``) sits immediately before
each of the five real agents. Every approval node is *always* present in
the topology — whether a given run actually pauses there is a runtime
policy decision made by ``PlanExecutor``, not a structural one; see
``approval_node_names()`` below, which the DI layer feeds straight into
``GraphConfig.interrupt_before`` so LangGraph always stops there, and
``PlanExecutor`` decides whether to surface that stop to a human or
transparently resume past it.
"""

from langgraph.graph import END

from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.approval_node import ApprovalNode
from backend.orchestration.nodes.browser_agent_node import BrowserAgentNode
from backend.orchestration.nodes.executive_summary_agent_node import (
    ExecutiveSummaryAgentNode,
)
from backend.orchestration.nodes.file_agent_node import FileAgentNode
from backend.orchestration.nodes.placeholders import EndNode
from backend.orchestration.nodes.planner_agent_node import PlannerAgentNode
from backend.orchestration.nodes.report_agent_node import ReportAgentNode
from backend.orchestration.nodes.sql_agent_node import SQLAgentNode

_GATED_NODE_NAMES = ("file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent")


def approval_node_names() -> list[str]:
    """The name of every approval interrupt point in the default graph, in topology order.

    Used by DI (``backend.dependencies.orchestration``) to populate
    ``GraphConfig.interrupt_before`` — kept here, next to the topology
    that defines them, instead of duplicated as a literal list elsewhere.
    """
    return [ApprovalNode(name).name for name in _GATED_NODE_NAMES]


def build_default_graph(
    builder: GraphBuilder,
    planner_agent_node: PlannerAgentNode,
    file_agent_service: FileAgentService,
    sql_agent_service: SQLAgentService,
    browser_agent_service: BrowserAgentService,
    report_agent_service: ReportAgentService,
    executive_summary_service: ExecutiveSummaryService,
) -> GraphBuilder:
    """Wire Planner -> Approval -> FileAgent -> Approval -> SQLAgent -> Approval ->
    BrowserAgent -> Approval -> ReportAgent -> Approval -> ExecutiveSummaryAgent -> End."""
    planner = planner_agent_node
    approval_file = ApprovalNode("file_agent")
    file_agent = FileAgentNode(file_agent_service)
    approval_sql = ApprovalNode("sql_agent")
    sql_agent = SQLAgentNode(sql_agent_service)
    approval_browser = ApprovalNode("browser_agent")
    browser_agent = BrowserAgentNode(browser_agent_service)
    approval_report = ApprovalNode("report_agent")
    report_agent = ReportAgentNode(report_agent_service)
    approval_executive_summary = ApprovalNode("executive_summary_agent")
    executive_summary_agent = ExecutiveSummaryAgentNode(executive_summary_service)
    end = EndNode()

    for node in (
        planner,
        approval_file,
        file_agent,
        approval_sql,
        sql_agent,
        approval_browser,
        browser_agent,
        approval_report,
        report_agent,
        approval_executive_summary,
        executive_summary_agent,
        end,
    ):
        builder.add_node(node)

    builder.set_entry_point(planner.name)
    builder.add_edge(planner.name, approval_file.name)
    builder.add_edge(approval_file.name, file_agent.name)
    builder.add_edge(file_agent.name, approval_sql.name)
    builder.add_edge(approval_sql.name, sql_agent.name)
    builder.add_edge(sql_agent.name, approval_browser.name)
    builder.add_edge(approval_browser.name, browser_agent.name)
    builder.add_edge(browser_agent.name, approval_report.name)
    builder.add_edge(approval_report.name, report_agent.name)
    builder.add_edge(report_agent.name, approval_executive_summary.name)
    builder.add_edge(approval_executive_summary.name, executive_summary_agent.name)
    builder.add_edge(executive_summary_agent.name, end.name)
    builder.add_edge(end.name, END)

    return builder
