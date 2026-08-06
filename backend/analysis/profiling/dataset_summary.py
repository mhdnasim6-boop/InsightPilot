"""Adapts a cleaning-layer ``DatasetProfile`` into the analysis layer's ``DatasetSummary``."""

from backend.analysis.models.dataset_summary import DatasetSummary
from backend.cleaning.models.profile import DatasetProfile


def build_dataset_summary(profile: DatasetProfile) -> DatasetSummary:
    """Build a ``DatasetSummary`` entirely from an existing ``DatasetProfile``.

    Zero DataFrame access here — every field already exists on the
    profile computed by ``DatasetProfilingService``.
    """
    return DatasetSummary(
        row_count=profile.row_count,
        column_count=profile.column_count,
        numeric_columns=sorted(profile.numeric_summary),
        categorical_columns=sorted(profile.categorical_summary),
        missing_values=int(profile.missing_value_summary.get("total_missing", 0)),
        memory_usage_bytes=profile.memory_usage_bytes,
        duplicate_count=int(profile.duplicate_summary.get("duplicate_row_count", 0)),
        data_types=dict(profile.data_types),
    )
