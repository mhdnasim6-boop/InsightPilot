"""Summarizes data quality from already-computed validation + metadata results.

Pure arithmetic aggregation of facts already extracted elsewhere — not a
judgment call, and not AI reasoning.
"""

from typing import Any

from backend.ingestion.metadata.result import DatasetMetadataResult
from backend.ingestion.validators.result import DatasetValidationResult


def build_quality_summary(
    validation_result: DatasetValidationResult, metadata_result: DatasetMetadataResult
) -> dict[str, Any]:
    """Combine validation issue counts and missing-value stats into one compact summary."""
    total_missing = sum(column.null_count for column in metadata_result.columns)
    total_cells = metadata_result.row_count * metadata_result.column_count
    missing_percentage = round((total_missing / total_cells) * 100, 2) if total_cells > 0 else 0.0

    return {
        "is_valid": validation_result.is_valid,
        "error_count": len(validation_result.errors),
        "warning_count": len(validation_result.warnings),
        "total_missing_values": total_missing,
        "missing_value_percentage": missing_percentage,
    }
