"""Integration tests for ChatService: answer real questions against a real,
ingested/cleaned/analyzed/visualized dataset, using only MockProvider — no
external AI, matching every other AI-touching test in this project.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.result import AnalysisResult
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.chatbot.context.models import ChatContext, ChatMessage
from backend.chatbot.retrieval.classifier import Intent
from backend.chatbot.services.chat_service import ChatService
from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from config.settings import Settings


class _CountingAIService:
    """Wraps a real AIService and counts calls, to prove the refusal path never calls it."""

    def __init__(self, real: AIService) -> None:
        self._real = real
        self.call_count = 0

    async def generate(self, request: AIRequest, provider_name: str | None = None) -> AIResponse:
        self.call_count += 1
        return await self._real.generate(request, provider_name)


def _make_chat_service() -> tuple[ChatService, _CountingAIService]:
    settings = Settings()
    counting_ai_service = _CountingAIService(AIService(ProviderFactory(settings), settings))
    service = ChatService(counting_ai_service, PromptManager())  # type: ignore[arg-type]
    return service, counting_ai_service


def _make_analysis_pipeline(tmp_path: Path) -> tuple[CleaningOutcome, AnalysisResult]:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(
        "date,region,revenue\n"
        "2024-01-01,East,100\n2024-02-01,East,150\n2024-03-01,East,200\n"
        "2024-01-01,West,50\n2024-02-01,West,90\n2024-03-01,West,9000\n"
    )

    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(
        ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store
    )
    analysis_service = AnalysisService(
        ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(AggregationEngine()),
    )

    dataset = ingestion_service.ingest(str(csv_file), dataset_name="sales.csv")
    outcome = cleaning_service.clean(dataset)
    result = analysis_service.analyze(outcome)
    return outcome, result


def test_ask_refuses_without_calling_ai_when_data_is_missing() -> None:
    async def scenario() -> None:
        service, ai_service = _make_chat_service()
        context = ChatContext(session_id="s1")

        response = await service.ask("What are the KPIs?", context)

        assert response.answerable is False
        assert response.confidence == 0.0
        assert response.intent == Intent.KPI
        assert ai_service.call_count == 0

    asyncio.run(scenario())


def test_ask_answers_general_question_with_no_context() -> None:
    async def scenario() -> None:
        service, ai_service = _make_chat_service()
        context = ChatContext(session_id="s1")

        response = await service.ask("hello, what can you do?", context)

        assert response.answerable is True
        assert response.intent == Intent.GENERAL
        assert ai_service.call_count == 1

    asyncio.run(scenario())


def test_ask_kpi_question_against_real_analysis(tmp_path: Path) -> None:
    async def scenario() -> None:
        outcome, result = _make_analysis_pipeline(tmp_path)
        service, ai_service = _make_chat_service()
        context = ChatContext(session_id="s1", selected_dataset=outcome.dataset, analysis_result=result)

        response = await service.ask("What are the key KPIs?", context)

        assert response.answerable is True
        assert response.intent == Intent.KPI
        assert response.confidence == 1.0
        assert response.referenced_kpis == [kpi.name for kpi in result.kpis]
        assert response.referenced_datasets == ["sales.csv"]
        assert ai_service.call_count == 1
        # MockProvider echoes the prompt, so the referenced KPI names must appear in the answer.
        assert result.kpis[0].name in response.answer

    asyncio.run(scenario())


def test_ask_anomaly_question_detects_the_seeded_outlier(tmp_path: Path) -> None:
    async def scenario() -> None:
        outcome, result = _make_analysis_pipeline(tmp_path)
        service, _ = _make_chat_service()
        context = ChatContext(session_id="s1", selected_dataset=outcome.dataset, analysis_result=result)

        response = await service.ask("Are there any anomalies in revenue?", context)

        assert response.answerable is True
        assert response.intent == Intent.ANOMALY
        assert "revenue" in response.answer

    asyncio.run(scenario())


def test_ask_visualization_question_without_visualization_result_refuses(tmp_path: Path) -> None:
    async def scenario() -> None:
        outcome, result = _make_analysis_pipeline(tmp_path)
        service, ai_service = _make_chat_service()
        context = ChatContext(session_id="s1", selected_dataset=outcome.dataset, analysis_result=result)

        response = await service.ask("Show me a chart", context)

        assert response.answerable is False
        assert response.intent == Intent.VISUALIZATION
        assert ai_service.call_count == 0

    asyncio.run(scenario())


def test_ask_includes_conversation_history_in_the_prompt(tmp_path: Path) -> None:
    async def scenario() -> None:
        outcome, result = _make_analysis_pipeline(tmp_path)
        service, _ = _make_chat_service()

        history = [ChatMessage(role="user", content="What dataset is this?", timestamp=datetime.now(UTC))]
        context = ChatContext(
            session_id="s1", selected_dataset=outcome.dataset, analysis_result=result, conversation_history=history
        )

        response = await service.ask("What are the KPIs?", context)

        assert "What dataset is this?" in response.answer  # MockProvider echoes the whole prompt

    asyncio.run(scenario())


def test_ask_suggests_follow_up_questions_only_when_answerable() -> None:
    async def scenario() -> None:
        service, _ = _make_chat_service()

        refusal = await service.ask("What are the KPIs?", ChatContext(session_id="s1"))
        answer = await service.ask("hello", ChatContext(session_id="s1"))

        assert refusal.suggested_follow_up_questions == []
        assert answer.suggested_follow_up_questions != []

    asyncio.run(scenario())
