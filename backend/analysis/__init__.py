"""Reusable business analysis framework: turns a cleaned ``BusinessDataset``
(via a ``CleaningOutcome``) into a structured, deterministic ``AnalysisResult``.

Future visualization, reporting, chatbot, and AI-agent code must consume
``AnalysisResult`` — never re-analyze a raw DataFrame themselves.
``backend.services.analysis_service.AnalysisService`` is the only entry
point. No visualization, report generation, dashboards, or AI-generated
insights live here — every number this package produces is deterministic
and reproducible.
"""
