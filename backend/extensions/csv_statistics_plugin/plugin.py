"""CSV Statistics Plugin — a complete, self-contained demo plugin.

Lives entirely outside ``backend/`` core (and outside ``backend/plugins/``,
the SDK itself) — the only InsightPilot code it imports is the SDK's own
public surface (``Plugin``/``PluginContext``/manifest models) and the
``Tool`` ABC every real, first-party tool already subclasses. Everything
else here (the input/output models, the tool, the analyzer) is entirely
this plugin's own code, exactly what a real third-party package would
ship.

Registers exactly what its own manifest declares: one Tool
(``csv_row_count`` — counts rows/columns in raw CSV text, no filesystem
or other core service access) and one Analyzer (``csv_basic_statistics``
— a small, named statistics dict computed from a ``BusinessDataset``
already in memory, per this phase's own "no DataFrame access" input
constraint).

``PLUGIN`` is the one, fixed-name module attribute ``PluginLoader``
looks for — see ``backend.plugins.discovery.loader``'s own docstring.
"""

import csv
import io

from pydantic import BaseModel

from backend.ingestion.models.dataset import BusinessDataset
from backend.plugins.interfaces.plugin import Plugin
from backend.plugins.interfaces.plugin_context import PluginContext
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata
from backend.tools.base.tool import Tool


class CSVStatisticsInput(BaseModel):
    """Raw CSV text to count rows/columns in — this plugin's own input model."""

    csv_text: str


class CSVStatisticsOutput(BaseModel):
    """This plugin's own output model — never a core InsightPilot model."""

    row_count: int
    column_count: int
    column_names: list[str]


class CSVRowCountTool(Tool[CSVStatisticsInput, CSVStatisticsOutput]):
    """Counts rows/columns in raw CSV text. Self-contained — no other service."""

    name = "csv_row_count"
    description = "Counts rows and columns in raw CSV text (demo Tool contributed by a plugin)."
    input_model = CSVStatisticsInput
    output_model = CSVStatisticsOutput

    async def execute(self, tool_input: CSVStatisticsInput) -> CSVStatisticsOutput:
        rows = list(csv.reader(io.StringIO(tool_input.csv_text)))
        if not rows:
            return CSVStatisticsOutput(row_count=0, column_count=0, column_names=[])
        header, *data_rows = rows
        return CSVStatisticsOutput(row_count=len(data_rows), column_count=len(header), column_names=header)


class CSVBasicStatisticsAnalyzer:
    """A demo Analyzer: a small, named statistics dict from an already-ingested dataset.

    Conforms structurally to ``backend.plugins.interfaces.plugin_context.AnalyzerExtension``
    — reads only ``BusinessDataset``'s own already-computed fields
    (``row_count``, ``columns``), never a DataFrame.
    """

    def analyze(self, dataset: BusinessDataset) -> dict[str, float]:
        return {"row_count": float(dataset.row_count), "column_count": float(len(dataset.columns))}


class CSVStatisticsPlugin(Plugin):
    """The demo plugin: registers one Tool and one Analyzer, nothing else."""

    def metadata(self) -> PluginManifest:
        return PluginManifest(
            metadata=PluginMetadata(
                id="csv_statistics_plugin",
                name="CSV Statistics Plugin",
                version="1.0.0",
                author="InsightPilot Samples",
                description=(
                    "Demonstrates the Plugin SDK: registers a csv_row_count Tool "
                    "and a csv_basic_statistics Analyzer."
                ),
                tags=["demo", "csv", "statistics"],
            ),
            compatible_version="0.1.0",
            provides=[ExtensionKind.TOOL, ExtensionKind.ANALYZER],
            dependencies=[],
        )

    def initialize(self) -> None:
        """No external resources to acquire — this plugin is fully self-contained."""

    def register(self, context: PluginContext) -> None:
        context.register_tool(CSVRowCountTool())
        context.register_analyzer("csv_basic_statistics", CSVBasicStatisticsAnalyzer())

    def shutdown(self) -> None:
        """No resources to release."""


PLUGIN = CSVStatisticsPlugin()
