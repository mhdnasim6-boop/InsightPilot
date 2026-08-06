"""Reusable data ingestion layer: converts any supported data source into a
standardized ``BusinessDataset``.

Future agents (File, Cleaning, Analysis, Visualization, Report — none of
which exist yet) must never read a file, open a database connection, or
call pandas directly. They consume `BusinessDataset` objects produced by
`backend.services.ingestion_service.IngestionService`, the only entry
point into this package. No AI reasoning, cleaning, or business logic
lives here — only loading, validating, and describing data.
"""
