"""Structural validation for ingestion: unsupported extensions, missing/empty
source files, and malformed DataFrames (empty schema, duplicate columns).
Returns rich results (``DatasetValidationResult``), never a bare boolean.
"""
