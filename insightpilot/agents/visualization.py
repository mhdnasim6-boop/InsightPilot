"""Visualization Agent: the LLM picks a chart type and columns; code validates it and Plotly draws it."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..providers.base import AIProvider, StructuredOutputError
from ..schemas import ChartSpec
from ..tools.chart_tool import build_chart, default_chart_spec, validate_chart_spec
from .common import audit, ran

VIZ_PROMPT = """You are the Visualization agent. Choose ONE chart for a query result.
chart_type: line (trend over time), bar (compare categories), grouped_bar (categories split by a second
category; needs `color`), scatter (two numeric columns), pie (only for 6 or fewer parts of a whole).
x, y and color must be column names from the result; y must be numeric. Give a short, descriptive title."""


def make_visualization(provider: AIProvider):
    def visualization(state: dict) -> dict:
        res = state.get("analysis_result") or {}
        cols, rows = res.get("columns", []), res.get("rows", [])
        update: dict = {"agents_run": ran(state, "visualization")}
        if len(rows) < 2:
            update["audit"] = [audit("visualization", "skipped", "fewer than 2 rows")]
            return update
        spec = None
        try:
            proposal = provider.structured(
                [SystemMessage(content=VIZ_PROMPT),
                 HumanMessage(content=f"Question: {res.get('question', '')}\nColumns: {cols}\nFirst rows: {rows[:5]}")],
                ChartSpec)
            spec = validate_chart_spec(proposal.model_dump(), cols, rows)
        except StructuredOutputError as exc:
            update["errors"] = [f"visualization: used default chart ({exc})"]
        if spec is None:
            spec = default_chart_spec(cols, rows)
        if spec is None:
            update["audit"] = [audit("visualization", "skipped", "no sensible chart")]
            return update
        fig = build_chart(spec, cols, rows)
        update.update(chart_spec=spec, visualization=fig.to_json(),
                      audit=[audit("visualization", "ok", f"{spec['chart_type']}: {spec['y']} by {spec['x']}")])
        return update

    return visualization
