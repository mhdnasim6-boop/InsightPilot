"""The one input every chart generator receives."""

from dataclasses import dataclass

import pandas as pd

from backend.analysis.models.result import AnalysisResult


@dataclass
class ChartContext:
    """Everything a chart generator might need. Not every generator uses every field.

    ``dataframe`` is only present when a ``BusinessDataset`` was supplied
    to ``VisualizationService`` and its DataFrame could be resolved —
    generators that need real values (bar/scatter/histogram/pie) must
    treat it as optional and report themselves not applicable without it.
    """

    analysis_result: AnalysisResult
    dataframe: pd.DataFrame | None = None
