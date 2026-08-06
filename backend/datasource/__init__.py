"""Reusable connectivity to external data sources — SQL today, others later.

Every data source under this package produces a ``BusinessDataset`` via
``IngestionService`` — the same abstraction file-based ingestion uses.
No agent (Planner, Chat, Analysis, Visualization) imports anything from
this package directly; they only ever see the ``BusinessDataset`` that
results.
"""
