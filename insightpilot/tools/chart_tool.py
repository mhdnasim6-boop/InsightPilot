"""Chart building with Plotly. The LLM only picks a specification; this code draws it."""
from __future__ import annotations

import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_TIME_NAME = re.compile(r"date|month|year|week|day|period|quarter", re.I)
_ISO = re.compile(r"^\d{4}-\d{2}(-\d{2})?")


def _frame(columns: list[str], rows: list[list]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def _numeric(df: pd.DataFrame, c: str) -> bool:
    return bool(pd.to_numeric(df[c], errors="coerce").notna().all()) and len(df) > 0


def _time_like(df: pd.DataFrame, c: str) -> bool:
    return bool(_TIME_NAME.search(c)) or bool(df[c].astype(str).map(lambda v: bool(_ISO.match(v))).all())


def _pretty(name: str) -> str:
    return name.replace("_", " ")


def default_chart_spec(columns: list[str], rows: list[list]) -> dict | None:
    """Rule-based chart choice, used when the LLM's choice is missing or invalid."""
    if len(rows) < 2 or len(columns) < 2:
        return None
    df = _frame(columns, rows)
    numeric = [c for c in columns if _numeric(df, c)]
    if not numeric:
        return None
    y = numeric[-1]
    x = next((c for c in columns if c != y), None)
    if x is None:
        return None
    chart = "line" if _time_like(df, x) else "bar"
    return {"chart_type": chart, "x": x, "y": y, "color": None, "title": f"{_pretty(y)} by {_pretty(x)}"}


def validate_chart_spec(spec: dict, columns: list[str], rows: list[list]) -> dict | None:
    """Return a cleaned spec, or None if it does not fit the result table."""
    x, y, color = spec.get("x"), spec.get("y"), spec.get("color")
    if x not in columns or y not in columns or x == y:
        return None
    df = _frame(columns, rows)
    if not _numeric(df, y):
        return None
    if color is not None and color not in columns:
        color = None
    kind = spec.get("chart_type")
    if kind == "scatter" and not _numeric(df, x):
        return None
    if kind == "pie" and (len(rows) > 6 or (pd.to_numeric(df[y]) < 0).any()):
        return None
    if kind == "grouped_bar" and color is None:
        return None
    return {"chart_type": kind, "x": x, "y": y, "color": color, "title": spec.get("title") or f"{_pretty(y)} by {_pretty(x)}"}


def build_chart(spec: dict, columns: list[str], rows: list[list]) -> go.Figure:
    df = _frame(columns, rows)
    df[spec["y"]] = pd.to_numeric(df[spec["y"]])
    x, y, color, kind = spec["x"], spec["y"], spec.get("color"), spec["chart_type"]
    labels = {c: _pretty(c) for c in columns}
    if kind == "line":
        fig = px.line(df.sort_values(x), x=x, y=y, color=color, markers=True, labels=labels)
    elif kind == "scatter":
        fig = px.scatter(df, x=x, y=y, color=color, labels=labels)
    elif kind == "pie":
        fig = px.pie(df, names=x, values=y)
    elif kind == "grouped_bar":
        fig = px.bar(df, x=x, y=y, color=color, barmode="group", labels=labels)
    else:
        d = df if _time_like(df, x) else df.sort_values(y, ascending=False)
        fig = px.bar(d, x=x, y=y, color=color, labels=labels)
    fig.update_layout(title=spec["title"], template="plotly_white", margin=dict(l=40, r=20, t=60, b=40), height=380)
    return fig
