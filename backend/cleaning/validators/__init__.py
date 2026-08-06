"""Post-cleaning structural validation.

Reuses ``backend.ingestion.validators.checks`` rather than reimplementing
structural checks — a cleaned DataFrame is still just a DataFrame, so the
same rules (no columns, no rows, duplicate column names) apply.
"""
