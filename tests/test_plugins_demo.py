"""Tests for the demo plugin (backend/extensions/csv_statistics_plugin/)
itself, in isolation — its Tool, its Analyzer, and its manifest — proving
it is a genuinely complete, standalone plugin, not just something the
registry happens to load without error.
"""

import asyncio

from backend.extensions.csv_statistics_plugin.plugin import (
    PLUGIN,
    CSVBasicStatisticsAnalyzer,
    CSVRowCountTool,
    CSVStatisticsInput,
)
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType
from backend.plugins.manifest.plugin_metadata import ExtensionKind
from backend.utils.time import utc_now


def test_plugin_manifest_is_complete() -> None:
    manifest = PLUGIN.metadata()
    assert manifest.id == "csv_statistics_plugin"
    assert manifest.metadata.author
    assert manifest.metadata.version
    assert set(manifest.provides) == {ExtensionKind.TOOL, ExtensionKind.ANALYZER}


def test_csv_row_count_tool_counts_rows_and_columns() -> None:
    tool = CSVRowCountTool()
    result = asyncio.run(tool.execute(CSVStatisticsInput(csv_text="a,b,c\n1,2,3\n4,5,6\n7,8,9\n")))
    assert result.row_count == 3
    assert result.column_count == 3
    assert result.column_names == ["a", "b", "c"]


def test_csv_row_count_tool_handles_empty_input() -> None:
    tool = CSVRowCountTool()
    result = asyncio.run(tool.execute(CSVStatisticsInput(csv_text="")))
    assert result.row_count == 0
    assert result.column_count == 0


def test_csv_row_count_tool_self_describes() -> None:
    tool = CSVRowCountTool()
    assert tool.name == "csv_row_count"
    metadata = tool.metadata()
    assert metadata["name"] == "csv_row_count"
    assert "input_schema" in metadata


def test_csv_basic_statistics_analyzer_reads_dataset_fields() -> None:
    now = utc_now()
    dataset = BusinessDataset(
        dataset_id="d1", dataset_name="sales", source_type=SourceType.CSV, source_location="sales.csv",
        row_count=42, column_count=0, created_at=now, loaded_at=now,
    )
    analyzer = CSVBasicStatisticsAnalyzer()
    result = analyzer.analyze(dataset)
    assert result["row_count"] == 42.0
    assert result["column_count"] == 0.0


def test_plugin_register_wires_both_extensions() -> None:
    from backend.plugins.interfaces.plugin_context import PluginContext
    from backend.tools.registry.tool_registry import ToolRegistry

    tool_registry = ToolRegistry()
    context = PluginContext(tool_registry)

    PLUGIN.register(context)

    kinds = {e.kind for e in context.registered_extensions}
    assert kinds == {ExtensionKind.TOOL, ExtensionKind.ANALYZER}
    assert tool_registry.get("csv_row_count") is not None


def test_plugin_initialize_and_shutdown_do_not_raise() -> None:
    PLUGIN.initialize()
    PLUGIN.shutdown()
