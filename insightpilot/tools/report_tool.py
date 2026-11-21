"""PDF report generation (ReportLab). Fixed template; numbers come from the stored query result."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _chart(columns: list[str], rows: list[list]) -> Drawing | None:
    """A simple bar/line chart of the first text column against the last numeric column."""
    if len(rows) < 2 or len(columns) < 2:
        return None
    vals = [_num(r[-1]) for r in rows]
    if any(v is None for v in vals):
        return None
    rows, vals = rows[:12], vals[:12]
    d = Drawing(440, 190)
    timeish = any(k in columns[0].lower() for k in ("date", "month", "year", "week", "period"))
    if timeish:
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 40, 30, 380, 130
        lp.data = [[(i, v) for i, v in enumerate(vals)]]
        lp.lines[0].strokeColor = colors.HexColor("#2f6fdd")
        d.add(lp)
    else:
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = 40, 30, 380, 130
        bc.data = [vals]
        bc.categoryAxis.categoryNames = [str(r[0])[:12] for r in rows]
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.labels.fontSize = 7
        bc.bars[0].fillColor = colors.HexColor("#2f6fdd")
        d.add(bc)
    return d


def generate_report_pdf(path: Path, *, title: str, dataset_name: str, executive_summary: str,
                        key_findings: list[str], columns: list[str], rows: list[list], sql: str,
                        evidence: list[dict], limitations: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    story = [Paragraph(escape(title), styles["Title"]),
             Paragraph(f"Dataset: {escape(dataset_name)}", styles["Italic"]), Spacer(1, 10),
             Paragraph("Executive summary", styles["Heading2"]), Paragraph(escape(executive_summary), body)]
    if key_findings:
        story += [Paragraph("Key findings", styles["Heading2"])]
        story += [Paragraph("&bull; " + escape(f), body) for f in key_findings]
    if rows:
        story += [Paragraph("Key figures (calculated by SQL)", styles["Heading2"])]
        shown = rows[:15]
        data = [columns] + [[("" if v is None else (f"{v:,.2f}" if isinstance(v, float) else str(v))) for v in r] for r in shown]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eefb")),
                               ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                               ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 1), (-1, -1), "RIGHT")]))
        story += [t]
        if len(rows) > 15:
            story += [Paragraph(f"Showing 15 of {len(rows)} rows.", styles["Italic"])]
        chart = _chart(columns, shown)
        if chart is not None:
            story += [Spacer(1, 8), chart]
        story += [Spacer(1, 6), Paragraph("Query used: <font face='Courier' size='7'>" + escape(sql) + "</font>", body)]
    if evidence:
        story += [Paragraph("External context (possibly related; not proof of cause)", styles["Heading2"])]
        for e in evidence[:6]:
            date = e.get("published_date") or "date not available"
            story += [Paragraph(f"&bull; {escape(e.get('title') or e['url'])} &mdash; {escape(e.get('publisher',''))}, "
                                f"published {escape(str(date))}<br/><font size='7'>{escape(e['url'])}</font>", body)]
    story += [Paragraph("Limitations", styles["Heading2"]), Paragraph(escape(limitations), body)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                      bottomMargin=2 * cm, title=title).build(story)
    return path
