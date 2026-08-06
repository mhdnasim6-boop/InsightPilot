"""Hallucination prevention: decide *before* any prompt is built whether the
assistant actually has grounds to answer.

This is the primary defense against invented metrics/charts — not a
prompt instruction asking the model to behave. If the data an intent
needs doesn't exist, :class:`ContextValidator` says so and
:class:`~backend.chatbot.services.chat_service.ChatService` never calls
the AI at all for that turn.
"""

from collections.abc import Callable

from pydantic import BaseModel

from backend.chatbot.context.models import ChatContext
from backend.chatbot.retrieval.classifier import Intent


class Answerability(BaseModel):
    """Whether a classified intent can be honestly answered from a ``ChatContext``."""

    answerable: bool
    reason: str | None = None
    is_partial: bool = False
    """True when the relevant section exists but is marked not-applicable
    (e.g. ``TrendAnalysisResult.applicable=False``) — still answerable,
    just with an honest "not applicable" explanation rather than real
    numbers."""


_NO_DATASET = "No dataset has been uploaded yet. Upload one on the Upload page first."
_NO_ANALYSIS = "This dataset hasn't been analyzed yet. Run Analysis first, then ask again."
_NO_KPIS = "No KPIs have been computed for this dataset."
_NO_VISUALIZATION = "No charts have been generated for this dataset yet. Visit the Visualization page first."
_NO_PLAN = "No execution plan has been generated yet. Visit the Planning page first."
_NO_REPORT = "No report has been generated yet. Visit the Reports page first."
_NO_WORKFLOW = "No workflow is currently selected. Visit the Workflows page first."
_NO_REFLECTION = "No reflection has been generated yet. Visit the Reflection page first."
_NO_OPTIMIZATION = "No plan optimization has been run yet. Visit the Adaptive page first."


class ContextValidator:
    """Determines, per intent, whether a ``ChatContext`` contains grounds to answer."""

    def __init__(self) -> None:
        self._checks: dict[Intent, Callable[[ChatContext], Answerability]] = {
            Intent.SUMMARY: self._check_summary,
            Intent.KPI: self._check_kpi,
            Intent.TREND: self._check_trend,
            Intent.COMPARISON: self._check_comparison,
            Intent.ANOMALY: self._check_anomaly,
            Intent.CORRELATION: self._check_correlation,
            Intent.EXPLANATION: self._check_summary,
            Intent.VISUALIZATION: self._check_visualization,
            Intent.PLANNING: self._check_planning,
            Intent.REPORT: self._check_report,
            Intent.WORKFLOW: self._check_workflow,
            Intent.REFLECTION: self._check_reflection,
            Intent.OPTIMIZATION: self._check_optimization,
            Intent.GENERAL: self._check_general,
        }

    def check(self, context: ChatContext, intent: Intent) -> Answerability:
        """Return the :class:`Answerability` of ``intent`` given ``context``."""
        return self._checks.get(intent, self._check_general)(context)

    def _check_general(self, context: ChatContext) -> Answerability:
        return Answerability(answerable=True)

    def _check_summary(self, context: ChatContext) -> Answerability:
        if context.analysis_result is None and context.selected_dataset is None:
            return Answerability(answerable=False, reason=_NO_DATASET)
        return Answerability(answerable=True)

    def _check_kpi(self, context: ChatContext) -> Answerability:
        if context.analysis_result is None:
            return Answerability(answerable=False, reason=_NO_ANALYSIS)
        if not context.analysis_result.kpis:
            return Answerability(answerable=False, reason=_NO_KPIS)
        return Answerability(answerable=True)

    def _check_trend(self, context: ChatContext) -> Answerability:
        if context.analysis_result is None:
            return Answerability(answerable=False, reason=_NO_ANALYSIS)
        return Answerability(answerable=True, is_partial=not context.analysis_result.trends.applicable)

    def _check_comparison(self, context: ChatContext) -> Answerability:
        # Comparison always has descriptive statistics to fall back on (see
        # ContextBuilder._build_comparison), so it's never "not applicable" —
        # only correlations specifically may be.
        if context.analysis_result is None:
            return Answerability(answerable=False, reason=_NO_ANALYSIS)
        return Answerability(answerable=True, is_partial=not context.analysis_result.correlations.applicable)

    def _check_anomaly(self, context: ChatContext) -> Answerability:
        if context.analysis_result is None:
            return Answerability(answerable=False, reason=_NO_ANALYSIS)
        return Answerability(answerable=True, is_partial=not context.analysis_result.anomalies.applicable)

    def _check_correlation(self, context: ChatContext) -> Answerability:
        if context.analysis_result is None:
            return Answerability(answerable=False, reason=_NO_ANALYSIS)
        return Answerability(answerable=True, is_partial=not context.analysis_result.correlations.applicable)

    def _check_visualization(self, context: ChatContext) -> Answerability:
        if context.visualization_result is None or not context.visualization_result.charts:
            return Answerability(answerable=False, reason=_NO_VISUALIZATION)
        return Answerability(answerable=True)

    def _check_planning(self, context: ChatContext) -> Answerability:
        if context.execution_plan is None:
            return Answerability(answerable=False, reason=_NO_PLAN)
        return Answerability(answerable=True)

    def _check_report(self, context: ChatContext) -> Answerability:
        if context.report_document is None:
            return Answerability(answerable=False, reason=_NO_REPORT)
        return Answerability(answerable=True)

    def _check_workflow(self, context: ChatContext) -> Answerability:
        if context.workflow is None:
            return Answerability(answerable=False, reason=_NO_WORKFLOW)
        return Answerability(answerable=True)

    def _check_reflection(self, context: ChatContext) -> Answerability:
        if context.reflection_result is None:
            return Answerability(answerable=False, reason=_NO_REFLECTION)
        return Answerability(answerable=True)

    def _check_optimization(self, context: ChatContext) -> Answerability:
        if context.optimization_result is None:
            return Answerability(answerable=False, reason=_NO_OPTIMIZATION)
        return Answerability(answerable=True)
