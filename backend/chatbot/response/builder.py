"""Assembles the final ``ChatResponse``.

Confidence is computed deterministically here, never self-reported by the
model: 1.0 when the classified intent's data was fully applicable, 0.6
when it existed but was marked not-applicable (an honest partial answer,
e.g. "no time column, so trend analysis doesn't apply"), and this
function is never reached at all when the data didn't exist — that path
short-circuits to :meth:`build_refusal` before any AI call happens.
"""

from backend.ai.models.responses import AIResponse
from backend.chatbot.response.models import ChatResponse
from backend.chatbot.retrieval.classifier import Intent
from backend.chatbot.retrieval.context_builder import RetrievedContext
from backend.chatbot.validation.answerability import Answerability

_FULL_CONFIDENCE = 1.0
_PARTIAL_CONFIDENCE = 0.6
_REFUSAL_CONFIDENCE = 0.0

_FOLLOW_UPS: dict[Intent, list[str]] = {
    Intent.SUMMARY: ["What are the key KPIs?", "Are there any anomalies in this dataset?"],
    Intent.KPI: ["What's the trend for these metrics?", "How do these compare across categories?"],
    Intent.TREND: ["Are there any anomalies in this data?", "What's driving this trend?"],
    Intent.COMPARISON: ["Is there a correlation between these columns?", "What's the trend for these metrics?"],
    Intent.ANOMALY: ["What's driving this anomaly?", "Can you show me a chart of this?"],
    Intent.CORRELATION: ["What's the trend for these columns?", "Are there any anomalies here?"],
    Intent.EXPLANATION: ["Can you give me an executive summary?", "What are the key KPIs?"],
    Intent.VISUALIZATION: ["Can you explain this chart in more detail?", "What insights come from this chart?"],
    Intent.PLANNING: ["What's the estimated duration for this plan?", "What are the individual steps?"],
    Intent.REPORT: ["What sections does this report have?", "Give me a summary of this dataset."],
    Intent.WORKFLOW: ["What's the status of this workflow?", "What are the individual steps?"],
    Intent.REFLECTION: ["What were the weaknesses?", "What should be done differently next time?"],
    Intent.OPTIMIZATION: ["Which of these decisions were applied automatically?", "What's the plan's goal?"],
    Intent.GENERAL: ["Give me a summary of this dataset.", "What are the key KPIs?"],
}


class ResponseBuilder:
    """Builds the final, structured :class:`ChatResponse` for one chat turn."""

    def build_refusal(self, intent: Intent, answerability: Answerability) -> ChatResponse:
        """Build a response for a question the assistant cannot honestly answer.

        No AI call happens for this path — ``answerability.reason`` (a
        plain, deterministic string) becomes the entire answer.
        """
        return ChatResponse(
            answer=answerability.reason or "I don't have enough information to answer that yet.",
            confidence=_REFUSAL_CONFIDENCE,
            intent=intent,
            answerable=False,
        )

    def build(
        self,
        intent: Intent,
        ai_response: AIResponse,
        retrieved: RetrievedContext,
        answerability: Answerability,
    ) -> ChatResponse:
        """Build a response from a generated answer and the facts that grounded it."""
        confidence = _PARTIAL_CONFIDENCE if answerability.is_partial else _FULL_CONFIDENCE
        return ChatResponse(
            answer=ai_response.content,
            confidence=confidence,
            intent=intent,
            answerable=True,
            referenced_kpis=retrieved.referenced_kpis,
            referenced_charts=retrieved.referenced_charts,
            referenced_insights=retrieved.referenced_insights,
            referenced_datasets=retrieved.referenced_datasets,
            suggested_follow_up_questions=_FOLLOW_UPS.get(intent, _FOLLOW_UPS[Intent.GENERAL]),
            metadata=retrieved.metadata,
        )
