"""BrowserAgent: enriches a step with external context. Never business analysis.

Mirrors ``backend.agents.file``/``backend.agents.sql`` in shape:
``BrowserAgentService`` (``backend.agents.browser.services``) is the
only entry point both the REST layer and ``BrowserAgentNode`` use.
Unlike File/SQL, BrowserAgent's result shape (sources/summaries, no
dataset/analysis/report) is genuinely new, so this package defines its
own ``BrowserAgentResult``/``BrowserAgentResultStore`` rather than
reusing FileAgent's — but it still reuses FileAgent's
``InvalidAgentInputError``/``AgentExecutionNotFoundError`` directly (no
``exceptions/`` package here), since those exceptions were already
agent-agnostic in name and meaning. BrowserAgent never generates SQL,
never computes a KPI, never builds a chart, and never modifies an
``AnalysisResult`` — it only calls ``BrowserService`` and returns what
it found.
"""
