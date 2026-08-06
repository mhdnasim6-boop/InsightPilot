"""Report endpoints: generate, list, fetch, and export (JSON/Markdown).

Thin HTTP wrappers over the existing ``ReportService`` — no report-building
logic here. PDF/Word/PowerPoint exporters exist at the service layer as
placeholders only (see ``backend/reporting/exporters/placeholders.py``);
this phase does not expose them over HTTP, matching the "(JSON/Markdown)"
scope of the export endpoint.

Route order matters: ``/reports/templates`` and ``/reports/themes`` are
registered before ``/reports/{report_id}`` so FastAPI matches them as
literal paths rather than treating "templates"/"themes" as a report ID.
"""

from typing import Literal

from fastapi import APIRouter, Depends

from backend.dependencies.reporting import get_report_service, get_report_theme_registry
from backend.reporting.models.report_document import ReportDocument, ReportExportFormat
from backend.reporting.templates.report_template import (
    ReportTemplateType,
    list_template_types,
)
from backend.reporting.themes.registry import ReportThemeRegistry
from backend.schemas.report_request import ReportGenerateRequest
from backend.schemas.response import SuccessResponse
from backend.services.report_service import ReportService

router = APIRouter(prefix="/reports")

_EXPORTABLE_FORMATS: dict[str, ReportExportFormat] = {
    "json": ReportExportFormat.JSON,
    "markdown": ReportExportFormat.MARKDOWN,
}


@router.post("", response_model=SuccessResponse[ReportDocument], summary="Build a ReportDocument")
async def generate_report(
    request: ReportGenerateRequest, report_service: ReportService = Depends(get_report_service)
) -> SuccessResponse[ReportDocument]:
    """Build, validate, and store a new report. Raises ReportValidationFailedError (422) if invalid."""
    document = report_service.build_report(
        request.dataset,
        request.cleaning_outcome,
        request.analysis_result,
        request.visualization_result,
        request.planner_output,
        request.template_type,
        request.theme,
        request.title,
        request.subtitle,
        request.author,
    )
    return SuccessResponse.ok(data=document, message="Report generated.")


@router.get("/templates", response_model=SuccessResponse[list[ReportTemplateType]], summary="List report templates")
async def get_report_templates() -> SuccessResponse[list[ReportTemplateType]]:
    """List every available report template type, for a frontend template picker."""
    return SuccessResponse.ok(data=list_template_types(), message="Report templates fetched.")


@router.get("/themes", response_model=SuccessResponse[list[str]], summary="List report theme names")
async def get_report_themes(
    theme_registry: ReportThemeRegistry = Depends(get_report_theme_registry),
) -> SuccessResponse[list[str]]:
    """List every registered report theme name, for a frontend theme picker."""
    return SuccessResponse.ok(data=theme_registry.list_names(), message="Report themes fetched.")


@router.get("", response_model=SuccessResponse[list[ReportDocument]], summary="List generated reports")
async def list_reports(
    report_service: ReportService = Depends(get_report_service),
) -> SuccessResponse[list[ReportDocument]]:
    """Return every report generated so far, most recently added first."""
    return SuccessResponse.ok(data=report_service.list_reports(), message="Reports fetched.")


@router.get("/{report_id}", response_model=SuccessResponse[ReportDocument], summary="Fetch one report")
async def get_report(
    report_id: str, report_service: ReportService = Depends(get_report_service)
) -> SuccessResponse[ReportDocument]:
    """Fetch a single report by ID. Raises ReportNotFoundError (404) if it doesn't exist."""
    return SuccessResponse.ok(data=report_service.get_report(report_id), message="Report fetched.")


@router.get(
    "/{report_id}/export",
    response_model=SuccessResponse[str],
    summary="Export a report as JSON or Markdown",
)
async def export_report(
    report_id: str,
    format: Literal["json", "markdown"] = "json",
    report_service: ReportService = Depends(get_report_service),
) -> SuccessResponse[str]:
    """Export a previously generated report as a JSON or Markdown string."""
    content = report_service.export_report(report_id, _EXPORTABLE_FORMATS[format])
    assert isinstance(content, str)  # guaranteed: JSON/MARKDOWN exporters always return str
    return SuccessResponse.ok(data=content, message=f"Report exported as {format}.")
