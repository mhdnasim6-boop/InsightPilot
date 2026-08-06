"""SQLAgent: orchestrates the existing pipeline for a SQL-sourced dataset.

Mirrors ``backend.agents.file`` exactly: ``SQLDataSourceService`` ->
``CleaningService`` -> ``AnalysisService`` -> ``VisualizationService`` ->
optionally ``ReportService``, for one ``ExecutionStep``. Never builds a
connection, runs a query, cleans a DataFrame, computes a statistic, or
renders a chart itself — every one of those already happens inside the
service it calls. Reuses ``AgentExecutionResult``/``AgentExecutionResultStore``/
``InvalidAgentInputError``/``AgentExecutionNotFoundError`` directly from
``backend.agents.file`` rather than redefining them — see the "models/
and exceptions/ folders are deliberately absent" note in
``backend/agents/sql/services/sql_agent_service.py``. ``SQLAgentService``
is the only entry point.
"""
