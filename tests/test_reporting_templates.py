"""Tests for the report template registry."""

import pytest

from backend.reporting.exceptions.errors import UnknownReportTemplateError
from backend.reporting.sections.section import ReportSectionKind
from backend.reporting.templates.report_template import (
    ReportTemplateType,
    get_template,
    list_template_types,
)


def test_list_template_types_returns_all_five() -> None:
    assert set(list_template_types()) == {
        ReportTemplateType.EXECUTIVE_SUMMARY,
        ReportTemplateType.BUSINESS_REPORT,
        ReportTemplateType.TECHNICAL_REPORT,
        ReportTemplateType.DATA_QUALITY_REPORT,
        ReportTemplateType.COMPARISON_REPORT,
    }


@pytest.mark.parametrize("template_type", list(ReportTemplateType))
def test_every_template_type_resolves_to_a_configured_template(template_type: ReportTemplateType) -> None:
    template = get_template(template_type)

    assert template.template_type == template_type
    assert template.name
    assert template.section_order  # never empty
    assert ReportSectionKind.OVERVIEW in template.required_sections


@pytest.mark.parametrize("template_type", list(ReportTemplateType))
def test_no_template_puts_appendix_in_its_own_section_order(template_type: ReportTemplateType) -> None:
    template = get_template(template_type)
    assert ReportSectionKind.APPENDIX not in template.section_order


@pytest.mark.parametrize("template_type", list(ReportTemplateType))
def test_required_sections_are_a_subset_of_section_order(template_type: ReportTemplateType) -> None:
    template = get_template(template_type)
    assert set(template.required_sections) <= set(template.section_order)


def test_get_template_raises_for_an_unregistered_template_type() -> None:
    with pytest.raises(UnknownReportTemplateError):
        get_template("not_a_real_template")  # type: ignore[arg-type]
