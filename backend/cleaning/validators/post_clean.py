"""Sanity-checks a DataFrame after a CleaningPipeline has run."""

import pandas as pd

from backend.ingestion.validators.checks import check_dataframe


def validate_cleaned_dataframe(dataframe: pd.DataFrame) -> list[str]:
    """Return human-readable warnings for any structural issue in the cleaned DataFrame."""
    return [f"{issue.code}: {issue.message}" for issue in check_dataframe(dataframe)]
