"""Reusable data cleaning framework: turns a ``BusinessDataset`` into a new,
cleaned ``BusinessDataset`` — never mutating the original.

Future agents (Analysis, Visualization, Report — none of which exist yet)
consume the cleaned dataset the same way they'd consume any
``BusinessDataset``: via ``backend.services.ingestion_service.IngestionService``.
``backend.services.cleaning_service.CleaningService`` is the only entry
point into this package. No AI reasoning, analysis, or visualization
lives here — only deterministic, rule-based cleaning and profiling.
"""
