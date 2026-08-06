"""Visualization providers: chart generators, recommendation/layout engines,
themes, exporters, and the visualization service.
"""

from functools import lru_cache

from fastapi import Depends

from backend.analysis.aggregations.engine import AggregationEngine
from backend.dependencies.analysis import get_aggregation_engine
from backend.dependencies.ingestion import get_ingestion_service
from backend.services.ingestion_service import IngestionService
from backend.services.visualization_service import VisualizationService
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.charts.registry import default_generators
from backend.visualization.exporters.image_placeholders import PNGExporter, SVGExporter
from backend.visualization.exporters.json_exporter import JSONExporter
from backend.visualization.exporters.plotly_exporter import PlotlyExporter
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from backend.visualization.themes.registry import ThemeRegistry


@lru_cache
def get_chart_generators(
    aggregation_engine: AggregationEngine = Depends(get_aggregation_engine),
) -> tuple[ChartGenerator, ...]:
    """Return the process-wide default chart generator tuple (stateless, safe to share).

    A tuple, not a list: this return value is itself an argument to the
    ``lru_cache``-decorated ``get_chart_recommendation_engine`` below,
    which needs every argument to be hashable.
    """
    return default_generators(aggregation_engine)


@lru_cache
def get_chart_recommendation_engine(
    generators: tuple[ChartGenerator, ...] = Depends(get_chart_generators),
) -> ChartRecommendationEngine:
    """Return the process-wide ChartRecommendationEngine singleton (stateless, safe to share)."""
    return ChartRecommendationEngine(generators)


@lru_cache
def get_layout_engine() -> LayoutEngine:
    """Return the process-wide LayoutEngine singleton (stateless, safe to share)."""
    return LayoutEngine()


@lru_cache
def get_theme_registry() -> ThemeRegistry:
    """Return the process-wide ThemeRegistry singleton."""
    return ThemeRegistry()


@lru_cache
def get_plotly_exporter() -> PlotlyExporter:
    """Return the process-wide PlotlyExporter singleton (stateless, safe to share)."""
    return PlotlyExporter()


@lru_cache
def get_json_exporter() -> JSONExporter:
    """Return the process-wide JSONExporter singleton (stateless, safe to share)."""
    return JSONExporter()


@lru_cache
def get_png_exporter() -> PNGExporter:
    """Return the process-wide PNGExporter singleton (stateless, safe to share)."""
    return PNGExporter()


@lru_cache
def get_svg_exporter() -> SVGExporter:
    """Return the process-wide SVGExporter singleton (stateless, safe to share)."""
    return SVGExporter()


def get_visualization_service(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    recommendation_engine: ChartRecommendationEngine = Depends(get_chart_recommendation_engine),
    layout_engine: LayoutEngine = Depends(get_layout_engine),
) -> VisualizationService:
    """Provide the VisualizationService — the only object that should be used for visualization."""
    return VisualizationService(ingestion_service, recommendation_engine, layout_engine)
