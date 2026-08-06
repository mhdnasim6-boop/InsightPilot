"""ReportAgent: orchestrates ReportService for one ExecutionStep. Never builds a report itself.

Mirrors ``backend.agents.file``/``backend.agents.sql``/``backend.agents.browser``
in shape: ``ReportAgentService`` (``backend.agents.report.services``) is the
only entry point both the REST layer and ``ReportAgentNode`` use.
``ReportAgentResult`` is a new shape (report_id/report_document, not
dataset/analysis/sources), so this package defines its own result and
its own store — but it still reuses FileAgent's
``InvalidAgentInputError``/``AgentExecutionNotFoundError`` directly (no
``exceptions/`` package here), the fourth agent to do so. ReportAgent
never computes a KPI, builds a chart, analyzes data, reads a file,
queries SQL, or searches the web — it only calls ``ReportService`` and
returns what it produced.
"""
