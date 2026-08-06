"""OptimizationReport: the complete output of one analysis pass."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.autonomous.models.autonomous_decision import AutonomousDecision
from backend.autonomous.models.bottleneck import Bottleneck
from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_action import OptimizationAction
from backend.autonomous.models.performance_profile import PerformanceProfile


class OptimizationReport(BaseModel):
    """One complete analysis pass: the platform's own performance snapshot, every
    detected bottleneck, every suggested action, and every advisory recommendation."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    performance_profile: PerformanceProfile
    decisions: list[AutonomousDecision] = Field(default_factory=list)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    actions: list[OptimizationAction] = Field(default_factory=list)
    recommendations: list[HealingRecommendation] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime
