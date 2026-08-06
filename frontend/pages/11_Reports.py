"""Reports page: build a ReportDocument from whatever pipeline outputs are
already in session state, browse it section by section, and export it.

Report generation is entirely deterministic — every word in a generated
report is text ``ReportBuilder`` already assembled from real
cleaning/analysis/visualization/planner results. No AI-written narrative
exists yet; that is a future phase's job, once this framework exists for
it to write into.
"""

import json
from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError, APIError
from frontend.components import render_api_error, render_kpi_cards
from frontend.layouts import page_header, render_sidebar, require_dataset
from frontend.state import get_dashboard_state
from frontend.utils import format_timestamp

_TEMPLATE_LABELS = {
    "executive_summary": "Executive Summary",
    "business_report": "Business Report",
    "technical_report": "Technical Report",
    "data_quality_report": "Data Quality Report",
    "comparison_report": "Comparison Report",
}


def _render_paragraph(block: dict[str, Any]) -> None:
    st.write(block["text"])


def _render_bullet_list(block: dict[str, Any]) -> None:
    for item in block["items"]:
        st.markdown(f"- {item}")


def _render_table(block: dict[str, Any]) -> None:
    if block.get("caption"):
        st.caption(block["caption"])
    headers = block.get("headers") or []
    if headers:
        st.dataframe(
            [dict(zip(headers, row, strict=False)) for row in block.get("rows", [])],
            width="stretch",
            hide_index=True,
        )


def _render_kpi_grid(block: dict[str, Any]) -> None:
    render_kpi_cards(block.get("kpis", []), columns_per_row=block.get("columns", 4))


def _render_chart_reference(block: dict[str, Any]) -> None:
    caption = f" — {block['caption']}" if block.get("caption") else ""
    st.info(f"Chart: **{block['title']}** ({block['chart_type']}){caption}")


def _render_image_placeholder(block: dict[str, Any]) -> None:
    st.caption(f"[Image placeholder: {block['caption']}]")


def _render_code_block_placeholder(block: dict[str, Any]) -> None:
    st.code(block.get("placeholder_text", ""), language=block.get("language"))


_BLOCK_RENDERERS = {
    "paragraph": _render_paragraph,
    "bullet_list": _render_bullet_list,
    "table": _render_table,
    "kpi_grid": _render_kpi_grid,
    "chart_reference": _render_chart_reference,
    "image_placeholder": _render_image_placeholder,
    "code_block_placeholder": _render_code_block_placeholder,
}


def _render_section(section: dict[str, Any]) -> None:
    for block in section.get("content_blocks", []):
        renderer = _BLOCK_RENDERERS.get(block.get("block_type", ""))
        if renderer is not None:
            renderer(block)
    if section.get("notes"):
        st.markdown("**Notes:**")
        for note in section["notes"]:
            st.caption(note)


def _render_generation_form(state: Any, client: APIClient, dataset: dict[str, Any]) -> None:
    st.subheader("Generate a Report")

    outcome = state.current_cleaning_outcome
    outcome_matches = outcome is not None and outcome["dataset"]["dataset_id"] == dataset["dataset_id"]

    analysis = state.current_analysis
    analysis_matches = analysis is not None and analysis.get("dataset_id") == dataset["dataset_id"]

    visualization = state.current_visualization
    visualization_matches = (
        analysis_matches
        and visualization is not None
        and visualization["visualization_result"]["analysis_id"] == analysis["analysis_id"]
    )

    st.caption(
        f"Available for '{dataset['dataset_name']}': "
        f"Cleaning {'✓' if outcome_matches else '✗'} · "
        f"Analysis {'✓' if analysis_matches else '✗'} · "
        f"Visualization {'✓' if visualization_matches else '✗'}"
    )

    try:
        template_types = client.list_report_templates()
    except APIClientError as exc:
        render_api_error(exc)
        template_types = ["business_report"]
    try:
        theme_names = client.list_report_themes()
    except APIClientError as exc:
        render_api_error(exc)
        theme_names = ["corporate"]

    col1, col2 = st.columns(2)
    with col1:
        template_type = st.selectbox(
            "Template", template_types, format_func=lambda value: _TEMPLATE_LABELS.get(value, value)
        )
    with col2:
        theme = st.selectbox("Theme", theme_names)

    title = st.text_input("Title (optional)", placeholder=f"{dataset['dataset_name']} Report")
    col3, col4 = st.columns(2)
    subtitle = col3.text_input("Subtitle (optional)")
    author = col4.text_input("Author (optional)")

    if st.button("Generate Report", type="primary"):
        with st.spinner("Building report..."):
            try:
                document = client.generate_report(
                    dataset=dataset,
                    cleaning_outcome=outcome if outcome_matches else None,
                    analysis_result=analysis if analysis_matches else None,
                    visualization_result=visualization["visualization_result"] if visualization_matches else None,
                    planner_output=state.current_plan,
                    template_type=template_type,
                    theme=theme,
                    title=title or None,
                    subtitle=subtitle or None,
                    author=author or None,
                )
            except APIError as exc:
                render_api_error(exc)
                issues = (exc.detail or {}).get("issues") if isinstance(exc.detail, dict) else None
                for issue in issues or []:
                    st.warning(issue["message"])
                return
            except APIClientError as exc:
                render_api_error(exc)
                return

        state.current_report = document
        state.add_activity(f"Generated a '{_TEMPLATE_LABELS.get(template_type, template_type)}' report.")
        st.success(f"Report '{document['title']}' generated.")


def _render_report_picker(state: Any, client: APIClient) -> None:
    try:
        reports = client.list_reports()
    except APIClientError as exc:
        render_api_error(exc)
        return
    if not reports:
        return

    with st.expander(f"Previously generated reports ({len(reports)})"):
        options = {f"{report['title']} — {format_timestamp(report.get('generated_at'))}": report for report in reports}
        chosen_label = st.selectbox("Load a previous report", list(options.keys()))
        if st.button("Load selected report"):
            state.current_report = options[chosen_label]


def _render_document(state: Any, client: APIClient, document: dict[str, Any]) -> None:
    st.divider()
    st.subheader(document["title"])
    if document.get("subtitle"):
        st.caption(document["subtitle"])

    meta1, meta2, meta3 = st.columns(3)
    meta1.caption(f"Generated: {format_timestamp(document.get('generated_at'))}")
    meta2.caption(f"Author: {document.get('author') or '—'}")
    meta3.caption(f"Theme: {document['theme']}")

    st.markdown("**Table of Contents**")
    for entry in document.get("table_of_contents", []):
        st.caption(f"{entry['order'] + 1}. {entry['title']}")

    all_sections = [*document.get("sections", []), *document.get("appendices", [])]
    if all_sections:
        tabs = st.tabs([section["title"] for section in all_sections])
        for tab, section in zip(tabs, all_sections, strict=False):
            with tab:
                _render_section(section)

    st.divider()
    st.subheader("Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download JSON",
            data=json.dumps(document, indent=2),
            file_name=f"{document['report_id']}.json",
            mime="application/json",
        )
    with col2:
        if st.button("Preview Markdown"):
            try:
                markdown = client.export_report(document["report_id"], "markdown")
            except APIClientError as exc:
                render_api_error(exc)
            else:
                st.session_state["_report_markdown_preview"] = markdown

    preview = st.session_state.get("_report_markdown_preview")
    if preview:
        with st.expander("Markdown preview", expanded=True):
            st.markdown(preview)


state = get_dashboard_state()
render_sidebar(state)
page_header("Reports", "Build a structured report from your cleaned, analyzed, and visualized data.", icon="📑")

dataset = require_dataset(state)

if dataset is not None:
    client = APIClient(state.backend_url)
    _render_generation_form(state, client, dataset)
    _render_report_picker(state, client)

    report = state.current_report
    if report is not None:
        _render_document(state, client, report)
    else:
        st.info("No report generated yet. Fill in the form above and click 'Generate Report'.")
