"""The conversational assistant's complete view of one chat turn.

``ChatContext`` never holds a raw DataFrame or a file path — only the
already-computed artifacts other services produced
(``BusinessDataset``, ``CleaningOutcome``, ``AnalysisResult``,
``VisualizationResult``, ``ExecutionPlan``). That is what makes "the
chatbot never analyzes raw data directly" a structural guarantee rather
than a convention: there is nothing in this model, or anything built on
top of it, that can reach a row of real data.

``report_document``/``workflow``/``reflection_result``/``optimization_result``
extend the original field list the same way ``cleaning_outcome`` already
did: each is an already-computed artifact from a platform-quality phase
built after this one (Reporting, Workflows/Phase 36, Reflection/Phase 31,
Adaptive Planning/Phase 32) that a user can reasonably ask about in the
same conversation — "summarize this report," "what's the workflow's
status," "how did the last run go," "what did the optimizer suggest."
Purely additive: every existing field, every existing intent, and every
call site that doesn't pass these keeps behaving exactly as before.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reporting.models.report_document import ReportDocument
from backend.visualization.models.result import VisualizationResult
from backend.workflows.models.workflow import Workflow


class ChatMessage(BaseModel):
    """One turn of the conversation, in either direction."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class ChatContext(BaseModel):
    """Everything the assistant may draw on to answer one question.

    ``cleaning_outcome`` extends the originally-specified field list:
    the phase's objective explicitly names ``CleaningOutcome`` as a
    knowledge source, and its step-by-step audit trail (which rules
    fired, how many duplicates were removed) isn't reconstructable from
    ``selected_dataset``/``analysis_result`` alone.

    There is deliberately no server-side store for any of this — the
    caller (the frontend) assembles a fresh ``ChatContext`` for every
    request from whatever it already has in its own session state,
    including ``conversation_history``. A persistent, cross-session
    memory component is out of scope for this phase; when one exists, it
    is simply what populates ``conversation_history``/``user_preferences``
    before calling :meth:`ChatService.ask` — this shape does not change.
    """

    session_id: str
    selected_dataset: BusinessDataset | None = None
    cleaning_outcome: CleaningOutcome | None = None
    analysis_result: AnalysisResult | None = None
    visualization_result: VisualizationResult | None = None
    execution_plan: ExecutionPlan | None = None
    report_document: ReportDocument | None = None
    workflow: Workflow | None = None
    reflection_result: ReflectionResult | None = None
    optimization_result: OptimizationResult | None = None
    conversation_history: list[ChatMessage] = Field(default_factory=list)
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
