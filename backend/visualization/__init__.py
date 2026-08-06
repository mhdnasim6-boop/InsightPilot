"""Reusable visualization framework: turns an ``AnalysisResult`` (and
optionally the cleaned ``BusinessDataset``) into structured, deterministic
chart specifications, a layout, and export forms.

Future reports, dashboards, chatbot responses, and executive summaries
must consume ``VisualizationResult`` — never build charts themselves.
``backend.services.visualization_service.VisualizationService`` is the
only entry point. No PDF/PowerPoint generation, dashboards, chatbot, or
LLM-generated narratives live here — every chart is deterministic and
Plotly is an internal implementation detail, isolated to ``exporters/``.
"""
