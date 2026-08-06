"""FileAgent: the first real LangGraph execution node.

Orchestrates the existing pipeline — ``IngestionService`` ->
``CleaningService`` -> ``AnalysisService`` -> ``VisualizationService`` ->
optionally ``ReportService`` — for one ``ExecutionStep``. Never reads a
CSV, cleans a DataFrame, computes a statistic, or renders a chart
itself; every one of those already happens inside the service it calls.
``FileAgentService`` (``backend/agents/file/services/``) is the only
entry point external callers (the REST layer, ``FileAgentNode``) use.
"""
