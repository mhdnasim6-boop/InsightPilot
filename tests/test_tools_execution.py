"""Execution tests: each tool calling its one real (not mocked) underlying service.

Mirrors the agent-level tests' own philosophy (test_file_agent.py etc.):
every tool here is exercised against the real service it wraps, never a
test double — these tests exist to prove each tool is a correct, thin
adapter, not a reimplementation.
"""

import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text

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
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
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
from backend.tools.models.inputs import (
    AnalyzeDatasetInput,
    CleanDatasetInput,
    GenerateExecutiveSummaryInput,
    GenerateReportInput,
    GenerateVisualizationInput,
    IngestDatasetInput,
    QueryDatabaseInput,
    SearchWebInput,
)
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


def _make_pipeline_services() -> tuple[IngestionService, CleaningService, AnalysisService, VisualizationService]:
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
    return ingestion_service, cleaning_service, analysis_service, visualization_service


def test_ingest_dataset_tool_calls_ingestion_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, *_ = _make_pipeline_services()
        tool = IngestDatasetTool(ingestion_service)

        dataset = await tool.execute(IngestDatasetInput(dataset_reference=str(csv_file)))

        assert dataset.row_count == 4
        assert tool.name == "ingest_dataset"
        assert tool.metadata()["description"]

    asyncio.run(scenario())


def test_clean_dataset_tool_calls_cleaning_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, cleaning_service, *_ = _make_pipeline_services()
        dataset = ingestion_service.ingest(str(csv_file))
        tool = CleanDatasetTool(cleaning_service)

        outcome = await tool.execute(CleanDatasetInput(dataset=dataset))

        assert outcome.result.quality_score == 100.0

    asyncio.run(scenario())


def test_analyze_dataset_tool_calls_analysis_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, cleaning_service, analysis_service, _ = _make_pipeline_services()
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)
        tool = AnalyzeDatasetTool(analysis_service)

        analysis = await tool.execute(AnalyzeDatasetInput(cleaning_outcome=cleaning_outcome))

        assert len(analysis.kpis) > 0

    asyncio.run(scenario())


def test_generate_visualization_tool_calls_visualization_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, cleaning_service, analysis_service, visualization_service = _make_pipeline_services()
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)
        analysis = analysis_service.analyze(cleaning_outcome)
        tool = GenerateVisualizationTool(visualization_service)

        visualization = await tool.execute(
            GenerateVisualizationInput(analysis_result=analysis, dataset=cleaning_outcome.dataset)
        )

        assert len(visualization.charts) > 0

    asyncio.run(scenario())


def test_generate_report_tool_calls_report_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, cleaning_service, analysis_service, visualization_service = _make_pipeline_services()
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)
        analysis = analysis_service.analyze(cleaning_outcome)
        visualization = visualization_service.generate(analysis, dataset=cleaning_outcome.dataset)
        report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
        tool = GenerateReportTool(report_service)

        document = await tool.execute(
            GenerateReportInput(
                dataset=cleaning_outcome.dataset,
                cleaning_outcome=cleaning_outcome,
                analysis_result=analysis,
                visualization_result=visualization,
            )
        )

        assert document.sections

    asyncio.run(scenario())


def _make_sqlite_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT, revenue REAL)"))
        connection.execute(text("INSERT INTO sales VALUES (1, 'East', 1000), (2, 'West', 200)"))
    engine.dispose()


def test_query_database_tool_via_table_name_calls_sql_data_source_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_sqlite_database(db_path)
        ingestion_service, *_ = _make_pipeline_services()
        sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
        tool = QueryDatabaseTool(sql_data_source_service)
        connection = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))

        dataset = await tool.execute(QueryDatabaseInput(connection=connection, table_name="sales"))

        assert dataset.row_count == 2

    asyncio.run(scenario())


def test_query_database_tool_via_query_calls_sql_data_source_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_sqlite_database(db_path)
        ingestion_service, *_ = _make_pipeline_services()
        sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
        tool = QueryDatabaseTool(sql_data_source_service)
        connection = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))

        dataset = await tool.execute(
            QueryDatabaseInput(connection=connection, query="SELECT * FROM sales WHERE region = 'East'")
        )

        assert dataset.row_count == 1

    asyncio.run(scenario())


def test_search_web_tool_calls_browser_service() -> None:
    async def scenario() -> None:
        tool = SearchWebTool(BrowserService(MockBrowserProvider()))

        outcome = await tool.execute(SearchWebInput(query="Acme Corp"))

        assert outcome.query == "Acme Corp"
        assert outcome.sources

    asyncio.run(scenario())


def test_generate_executive_summary_tool_calls_ai_service(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        ingestion_service, cleaning_service, analysis_service, visualization_service = _make_pipeline_services()
        dataset = ingestion_service.ingest(str(csv_file))
        cleaning_outcome = cleaning_service.clean(dataset)
        analysis = analysis_service.analyze(cleaning_outcome)
        visualization = visualization_service.generate(analysis, dataset=cleaning_outcome.dataset)
        report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
        document = report_service.build_report(
            cleaning_outcome.dataset,
            cleaning_outcome=cleaning_outcome,
            analysis_result=analysis,
            visualization_result=visualization,
        )

        settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
        ai_service = AIService(ProviderFactory(settings), settings)
        tool = GenerateExecutiveSummaryTool(ai_service, PromptManager())

        draft = await tool.execute(GenerateExecutiveSummaryInput(report_document=document))

        assert draft.executive_summary

    asyncio.run(scenario())
