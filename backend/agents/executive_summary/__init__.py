"""ExecutiveSummaryAgent: InsightPilot's first true AI-reasoning agent.

Every earlier agent (File/SQL/Browser/Report) is a thin orchestrator —
sequencing existing deterministic services with no reasoning of its own.
This one is different in kind: turning a report's already-computed facts
into a coherent business narrative genuinely requires language
understanding, so its one piece of real work is a single
``AIService.generate()`` call. Everything else mirrors every prior
agent's shape exactly: ``ExecutiveSummaryService``
(``backend.agents.executive_summary.services``) is the only entry point
both the REST layer and ``ExecutiveSummaryAgentNode`` use, and this
package reuses FileAgent's ``InvalidAgentInputError``/
``AgentExecutionNotFoundError`` directly (no ``exceptions/`` package
here) — the fifth agent to do so.

Grounding is structural, not just instructional: the agent only ever
sees text rendered from an already-validated ``ReportDocument`` (via the
existing ``MarkdownReportExporter`` — no new report-rendering logic) and
an optional ``BrowserAgentResult``'s own summaries. It never calls
``AnalysisService``, ``VisualizationService``, ``ReportBuilder``,
``CleaningService``, a SQL service, or ``BrowserService`` — there is
nothing in this package that could recompute analysis even by accident.
"""
