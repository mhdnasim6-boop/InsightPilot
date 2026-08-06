"""PluginContext: the only surface a Plugin's ``register()`` ever touches.

Every ``register_*`` method is completely typed against either a real,
existing InsightPilot interface (``Tool``, ``AIProvider``, ``ChartGenerator``,
the ``AgentService`` structural Protocol Phase 27 already established) or
a small, purpose-built ``Protocol`` defined here for extension kinds with
no existing interface to reuse (``Exporter``/``MemoryProvider``/
``ApprovalPolicyStrategy``/``Analyzer``/``Optimizer``) — never ``Any``.

Only ``register_tool()`` reaches a genuinely live, process-wide registry
(``ToolRegistry`` — the one existing registry in the whole codebase with
a public, runtime-safe ``register()`` method a plugin can call without
touching core business logic; see this module's own package docstring
in ``backend/plugins/__init__.py``). Every other kind has no such live,
publicly-mutable registry anywhere in InsightPilot today (``ProviderFactory``'s
provider map, the chart generator list, ``NodeDispatcher``'s agent map,
and ``ApprovalPolicy`` are all fixed at DI-wiring time, by design, in
earlier phases) — so those are recorded in ``PluginRegistry``'s own
catalog for discovery/introspection (``GET /plugins/{id}``) rather than
silently no-op'd or, worse, live-patched into modules a plugin has no
business reaching into. Wiring each of those live is a named Future
Extension, not a shortcut taken here.

Plugins never mutate a registry directly — every method here is the
*only* door in, and every call is recorded locally so
``PluginRegistry.load_all()`` can read back exactly what a plugin
contributed after ``register()`` returns.
"""

from typing import Any, Protocol

from backend.ingestion.models.dataset import BusinessDataset
from backend.memory.models.memory_item import MemoryItem
from backend.planning.models.plan import ExecutionPlan
from backend.plugins.lifecycle.lifecycle import RegisteredExtension
from backend.plugins.manifest.plugin_metadata import ExtensionKind
from backend.tools.base.tool import Tool
from backend.tools.registry.tool_registry import ToolRegistry


class AgentServiceExtension(Protocol):
    """The same structural contract ``NodeDispatcher.AgentService`` already established."""

    async def execute_step(self, step: object, session_id: str | None) -> object: ...


class AIProviderExtension(Protocol):
    """A minimal, name-bearing marker — the real contract is ``backend.ai.providers.base.AIProvider``."""

    provider_name: str


class ExporterExtension(Protocol):
    """One export operation, producing a serialized string from whatever domain object it accepts."""

    def export(self, data: object) -> str: ...


class MemoryProviderExtension(Protocol):
    """A minimal storage contract mirroring ``MemoryStore``'s own ``add``/``get``."""

    def add(self, item: MemoryItem) -> None: ...
    def get(self, memory_id: str) -> MemoryItem | None: ...


class ApprovalPolicyExtension(Protocol):
    """The same evaluation contract ``ApprovalPolicy.requires_approval`` already has."""

    def requires_approval(self, node_name: str) -> bool: ...


class AnalyzerExtension(Protocol):
    """Produces a small, named set of statistics from a ``BusinessDataset``.

    Deliberately not the full, internal ``AnalysisResult`` (five nested
    sub-models — ``DatasetSummary``/``DescriptiveStatistics``/
    ``TrendAnalysisResult``/``AnomalyAnalysisResult``/
    ``CorrelationAnalysisResult``): that shape is private to
    ``AnalysisService``'s own fixed pipeline, not a reasonable contract
    to hand a third-party plugin. A plain, named ``float`` mapping is a
    realistic, still fully-typed extension point.
    """

    def analyze(self, dataset: BusinessDataset) -> dict[str, float]: ...


class OptimizerExtension(Protocol):
    """Produces a (possibly adjusted) ``ExecutionPlan`` from one — mirrors Phase 32's own optimizer shape."""

    def optimize(self, plan: ExecutionPlan) -> ExecutionPlan: ...


class VisualizationExtension(Protocol):
    """The same structural contract ``ChartGenerator`` already established."""

    chart_type: object


class PluginContext:
    """The only object a Plugin's ``register()`` method ever receives."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._extensions: list[RegisteredExtension] = []

    @property
    def registered_extensions(self) -> list[RegisteredExtension]:
        """Everything registered through this context so far, in call order."""
        return list(self._extensions)

    def register_agent(self, name: str, agent: AgentServiceExtension) -> None:
        """Record an agent-service extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.AGENT, name, agent)

    def register_tool(self, tool: Tool[Any, Any]) -> None:
        """Register a real, immediately-usable Tool into the shared ToolRegistry."""
        self._tool_registry.register(tool)
        self._record(ExtensionKind.TOOL, tool.name, tool)

    def register_exporter(self, name: str, exporter: ExporterExtension) -> None:
        """Record an exporter extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.EXPORTER, name, exporter)

    def register_visualization(self, name: str, generator: VisualizationExtension) -> None:
        """Record a chart-generator extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.VISUALIZATION, name, generator)

    def register_ai_provider(self, name: str, provider: AIProviderExtension) -> None:
        """Record an AI-provider extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.AI_PROVIDER, name, provider)

    def register_memory_provider(self, name: str, provider: MemoryProviderExtension) -> None:
        """Record a memory-provider extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.MEMORY_PROVIDER, name, provider)

    def register_approval_policy(self, name: str, policy: ApprovalPolicyExtension) -> None:
        """Record an approval-policy extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.APPROVAL_POLICY, name, policy)

    def register_analyzer(self, name: str, analyzer: AnalyzerExtension) -> None:
        """Record an analyzer extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.ANALYZER, name, analyzer)

    def register_optimizer(self, name: str, optimizer: OptimizerExtension) -> None:
        """Record an optimizer extension. Cataloged only — see module docstring."""
        self._record(ExtensionKind.OPTIMIZER, name, optimizer)

    def _record(self, kind: ExtensionKind, name: str, extension: object) -> None:
        """The one place every ``register_*`` call lands — ``extension`` is accepted
        (and therefore type-checked at every call site above) but only its kind/name
        are cataloged; see this module's own docstring for why.
        """
        del extension
        self._extensions.append(RegisteredExtension(kind=kind, name=name))
