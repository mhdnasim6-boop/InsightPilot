"""The central, universal output of the business analysis framework.

Every future consumer (visualization, reports, a chatbot, an AI agent)
reads an ``AnalysisResult`` — never a raw DataFrame. Future analysis
modules should extend this model (add fields, or compose a subclass) —
never replace it or invent a parallel result type.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.insight import Insight
from backend.analysis.models.kpi import KPIResult
from backend.analysis.models.statistics import DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult


class AnalysisResult(BaseModel):
    """The complete, structured output of analyzing one cleaned dataset."""

    analysis_id: str
    dataset_id: str
    analysis_timestamp: datetime
    dataset_summary: DatasetSummary
    descriptive_statistics: DescriptiveStatistics
    kpis: list[KPIResult] = Field(default_factory=list)
    trends: TrendAnalysisResult
    anomalies: AnomalyAnalysisResult
    correlations: CorrelationAnalysisResult
    insights: list[Insight] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    execution_time: float
