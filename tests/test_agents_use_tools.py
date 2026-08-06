"""Integration tests: every agent calls tools, never a service directly.

Each real tool is wrapped in a small spy that records every call
(tool name + input) while still delegating to the real tool underneath
— so these tests prove the *sequence and shape* of tool calls an agent
makes, against real (not mocked) underlying services, mirroring every
other test file's "real services, no test doubles for business logic"
convention.
"""

import asyncio
from pathlib import Path
from typing import Any

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.report.execution.report_agent import ReportAgent
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.browser.providers.mock import MockBrowserProvider
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.sql_data_source_service import SQLDataSourceService
from backend.services.visualization_service import VisualizationService
from backend.tools.base.tool import Tool
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.tools.execution.query_database_tool import QueryDatabaseTool
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings

_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
)


class _SpyTool(Tool[Any, Any]):
    """Wraps a real tool, recording every call into a shared log before delegating."""

    def __init__(self, inner: Tool[Any, Any], log: list[str]) -> None:
        self._inner = inner
        self._log = log
        self.name = inner.name
        self.description = inner.description
        self.input_model = inner.input_model
        self.output_model = inner.output_model

    async def execute(self, tool_input: Any) -> Any:
        self._log.append(self.name)
        return await self._inner.execute(tool_input)


def _make_pipeline_tools(log: list[str]) -> tuple[IngestDatasetTool, CleanDatasetTool, AnalyzeDatasetTool, GenerateVisualizationTool, GenerateReportTool]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store)
    aggregation_engine = AggregationEngine()
    analysis_service = AnalysisService(
        ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(aggregation_engine),
    )
    visualization_service = VisualizationService(
        ingestion_service, ChartRecommendationEngine(default_generators(aggregation_engine)), LayoutEngine()
    )
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    return (
        _SpyTool(IngestDatasetTool(ingestion_service), log),  # type: ignore[return-value]
        _SpyTool(CleanDatasetTool(cleaning_service), log),  # type: ignore[return-value]
        _SpyTool(AnalyzeDatasetTool(analysis_service), log),  # type: ignore[return-value]
        _SpyTool(GenerateVisualizationTool(visualization_service), log),  # type: ignore[return-value]
        _SpyTool(GenerateReportTool(report_service), log),  # type: ignore[return-value]
    )


def test_file_agent_calls_ingest_clean_analyze_visualize_in_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        log: list[str] = []
        ingest, clean, analyze, visualize, report = _make_pipeline_tools(log)
        agent = FileAgent(ingest, clean, analyze, visualize, report, BusinessDatasetStore())

        step = ExecutionStep(
            step_id="s1", name="x", node_name="file_agent", inputs={"dataset_reference": str(csv_file)}
        )
        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["ingest_dataset", "clean_dataset", "analyze_dataset", "generate_visualization"]

    asyncio.run(scenario())


def test_file_agent_calls_generate_report_tool_only_when_requested(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        log: list[str] = []
        ingest, clean, analyze, visualize, report = _make_pipeline_tools(log)
        agent = FileAgent(ingest, clean, analyze, visualize, report, BusinessDatasetStore())

        step = ExecutionStep(
            step_id="s1",
            name="x",
            node_name="file_agent",
            inputs={"dataset_reference": str(csv_file), "generate_report": True},
        )
        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["ingest_dataset", "clean_dataset", "analyze_dataset", "generate_visualization", "generate_report"]

    asyncio.run(scenario())


def test_sql_agent_calls_query_database_then_the_shared_pipeline_tools(tmp_path: Path) -> None:
    async def scenario() -> None:
        from sqlalchemy import create_engine, text

        from backend.datasource.sql.models.connection_config import (
            DatabaseType,
            SQLConnectionConfig,
        )

        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT, revenue REAL)"))
            connection.execute(text("INSERT INTO sales VALUES (1, 'East', 1000), (2, 'West', 200)"))
        engine.dispose()

        log: list[str] = []
        dataframe_store = DataFrameStore()
        extractor = MetadataExtractor()
        ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
        cleaning_service = CleaningService(ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store)
        aggregation_engine = AggregationEngine()
        analysis_service = AnalysisService(
            ingestion_service,
            DescriptiveStatisticsEngine(),
            KPIEngine(),
            TrendEngine(),
            CorrelationEngine(),
            AnomalyEngine(),
            InsightEngine(aggregation_engine),
        )
        visualization_service = VisualizationService(
            ingestion_service, ChartRecommendationEngine(default_generators(aggregation_engine)), LayoutEngine()
        )
        report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
        clean = _SpyTool(CleanDatasetTool(cleaning_service), log)
        analyze = _SpyTool(AnalyzeDatasetTool(analysis_service), log)
        visualize = _SpyTool(GenerateVisualizationTool(visualization_service), log)
        report = _SpyTool(GenerateReportTool(report_service), log)

        sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
        query_tool = _SpyTool(QueryDatabaseTool(sql_data_source_service), log)

        agent = SQLAgent(query_tool, clean, analyze, visualize, report, BusinessDatasetStore())  # type: ignore[arg-type]
        connection_config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
        step = ExecutionStep(
            step_id="s1",
            name="x",
            node_name="sql_agent",
            inputs={"connection": connection_config.model_dump(mode="json"), "table_name": "sales"},
        )

        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["query_database", "clean_dataset", "analyze_dataset", "generate_visualization"]

    asyncio.run(scenario())


def test_browser_agent_calls_search_web_tool_once_per_query() -> None:
    async def scenario() -> None:
        log: list[str] = []
        tool = _SpyTool(SearchWebTool(BrowserService(MockBrowserProvider())), log)
        agent = BrowserAgent(tool)  # type: ignore[arg-type]

        step = ExecutionStep(
            step_id="s1",
            name="x",
            node_name="browser_agent",
            inputs={"companies": ["Acme Corp", "Globex"]},
        )
        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["search_web", "search_web"]

    asyncio.run(scenario())


def test_report_agent_calls_generate_report_tool_exactly_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataframe_store = DataFrameStore()
        extractor = MetadataExtractor()
        ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
        cleaning_service = CleaningService(ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store)
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)

        log: list[str] = []
        report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
        tool = _SpyTool(GenerateReportTool(report_service), log)
        agent = ReportAgent(tool)  # type: ignore[arg-type]

        step = ExecutionStep(
            step_id="s1",
            name="x",
            node_name="report_agent",
            inputs={
                "dataset": cleaning_outcome.dataset.model_dump(mode="json"),
                "cleaning_outcome": cleaning_outcome.model_dump(mode="json"),
                "report_config": {"template_type": "data_quality_report"},
            },
        )
        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["generate_report"]

    asyncio.run(scenario())


def test_executive_summary_agent_calls_generate_executive_summary_tool_exactly_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataframe_store = DataFrameStore()
        extractor = MetadataExtractor()
        ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
        cleaning_service = CleaningService(ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store)
        aggregation_engine = AggregationEngine()
        analysis_service = AnalysisService(
            ingestion_service,
            DescriptiveStatisticsEngine(),
            KPIEngine(),
            TrendEngine(),
            CorrelationEngine(),
            AnomalyEngine(),
            InsightEngine(aggregation_engine),
        )
        visualization_service = VisualizationService(
            ingestion_service, ChartRecommendationEngine(default_generators(aggregation_engine)), LayoutEngine()
        )
        report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)
        analysis = analysis_service.analyze(cleaning_outcome)
        visualization = visualization_service.generate(analysis, dataset=cleaning_outcome.dataset)
        document = report_service.build_report(
            cleaning_outcome.dataset,
            cleaning_outcome=cleaning_outcome,
            analysis_result=analysis,
            visualization_result=visualization,
        )

        log: list[str] = []
        settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
        ai_service = AIService(ProviderFactory(settings), settings)
        tool = _SpyTool(GenerateExecutiveSummaryTool(ai_service, PromptManager()), log)
        agent = ExecutiveSummaryAgent(tool)  # type: ignore[arg-type]

        step = ExecutionStep(
            step_id="s1",
            name="x",
            node_name="executive_summary_agent",
            inputs={"report_document": document.model_dump(mode="json")},
        )
        result = await agent.execute(step, session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert log == ["generate_executive_summary"]

    asyncio.run(scenario())
