"""Report templates: which sections a report includes, and in what order.

Mirrors ``backend.visualization.layouts.engine.LayoutEngine``'s four
layout types — "purely organizational groupings," never content
generation. A template never touches ``AnalysisResult``/
``VisualizationResult``; ``ReportBuilder`` is the only thing that does. A
plain dict registry (not a class) — closer in spirit to the Planner's
fixed prompt categories (``backend.agents.planner.prompts.templates``)
than to the Theme registry's open, user-extensible palette concept.
"""

from enum import Enum

from pydantic import BaseModel, Field

from backend.reporting.exceptions.errors import UnknownReportTemplateError
from backend.reporting.sections.section import ReportSectionKind

_S = ReportSectionKind


class ReportTemplateType(str, Enum):
    """Every report template this framework provides."""

    EXECUTIVE_SUMMARY = "executive_summary"
    BUSINESS_REPORT = "business_report"
    TECHNICAL_REPORT = "technical_report"
    DATA_QUALITY_REPORT = "data_quality_report"
    COMPARISON_REPORT = "comparison_report"


class ReportTemplate(BaseModel):
    """Which sections a report of this kind includes, in what order, and which are required.

    ``section_order`` never includes ``ReportSectionKind.APPENDIX`` —
    appendix content lives in ``ReportDocument.appendices``, a separate
    field from ``ReportDocument.sections``; ``include_appendix`` controls
    whether ``ReportBuilder`` populates it for this template.
    """

    template_type: ReportTemplateType
    name: str
    description: str
    section_order: list[ReportSectionKind] = Field(default_factory=list)
    required_sections: list[ReportSectionKind] = Field(default_factory=list)
    include_appendix: bool = True


_TEMPLATES: dict[ReportTemplateType, ReportTemplate] = {
    ReportTemplateType.EXECUTIVE_SUMMARY: ReportTemplate(
        template_type=ReportTemplateType.EXECUTIVE_SUMMARY,
        name="Executive Summary",
        description="A concise, high-level overview for decision-makers.",
        section_order=[_S.OVERVIEW, _S.KPIS, _S.CHARTS, _S.INSIGHTS],
        required_sections=[_S.OVERVIEW, _S.KPIS],
        include_appendix=False,
    ),
    ReportTemplateType.BUSINESS_REPORT: ReportTemplate(
        template_type=ReportTemplateType.BUSINESS_REPORT,
        name="Business Report",
        description="A well-rounded report covering the dataset, key metrics, charts, and findings.",
        section_order=[_S.OVERVIEW, _S.DATASET_SUMMARY, _S.KPIS, _S.CHARTS, _S.INSIGHTS],
        required_sections=[_S.OVERVIEW, _S.KPIS],
        include_appendix=True,
    ),
    ReportTemplateType.TECHNICAL_REPORT: ReportTemplate(
        template_type=ReportTemplateType.TECHNICAL_REPORT,
        name="Technical Report",
        description="Full analytical detail: dataset structure, cleaning, statistics, KPIs, charts, and insights.",
        section_order=[
            _S.OVERVIEW,
            _S.DATASET_SUMMARY,
            _S.CLEANING_SUMMARY,
            _S.ANALYSIS,
            _S.KPIS,
            _S.CHARTS,
            _S.INSIGHTS,
        ],
        required_sections=[_S.OVERVIEW, _S.DATASET_SUMMARY, _S.ANALYSIS],
        include_appendix=True,
    ),
    ReportTemplateType.DATA_QUALITY_REPORT: ReportTemplate(
        template_type=ReportTemplateType.DATA_QUALITY_REPORT,
        name="Data Quality Report",
        description="Focused on dataset structure and the cleaning pipeline's audit trail.",
        section_order=[_S.OVERVIEW, _S.DATASET_SUMMARY, _S.CLEANING_SUMMARY],
        required_sections=[_S.OVERVIEW, _S.DATASET_SUMMARY, _S.CLEANING_SUMMARY],
        include_appendix=True,
    ),
    ReportTemplateType.COMPARISON_REPORT: ReportTemplate(
        template_type=ReportTemplateType.COMPARISON_REPORT,
        name="Comparison Report",
        description=(
            "KPIs and charts featured first for comparison-style reading. Compares metrics and "
            "correlations within one dataset — no cross-dataset comparison exists yet."
        ),
        section_order=[_S.OVERVIEW, _S.KPIS, _S.CHARTS, _S.ANALYSIS, _S.INSIGHTS],
        required_sections=[_S.OVERVIEW, _S.KPIS, _S.CHARTS],
        include_appendix=False,
    ),
}


def get_template(template_type: ReportTemplateType) -> ReportTemplate:
    """Return the ``ReportTemplate`` for ``template_type``.

    Raises ``UnknownReportTemplateError`` if unrecognized — should never
    happen in practice since ``ReportTemplateType`` is a closed enum and
    every member is registered here; a defensive guard against the two
    drifting apart.
    """
    template = _TEMPLATES.get(template_type)
    if template is None:
        label = getattr(template_type, "value", template_type)
        raise UnknownReportTemplateError(f"Unknown report template: '{label}'.")
    return template


def list_template_types() -> list[ReportTemplateType]:
    """Return every available template type."""
    return sorted(_TEMPLATES, key=lambda template_type: template_type.value)
