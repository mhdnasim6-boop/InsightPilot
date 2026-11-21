"""Pydantic contracts between the LLM and the rest of the code.

Anything that controls the workflow (routing, cleaning fixes, chart choice,
email text) must pass through one of these models. Literal fields restrict the
model to a fixed set of values, so even a small local model cannot invent an
agent name or a cleaning operation.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

AgentName = Literal["data_cleaning", "data_analyst", "visualization", "research", "report_email"]
WORKER_AGENTS: tuple[str, ...] = ("data_cleaning", "data_analyst", "visualization", "research", "report_email")


class RoutingDecision(BaseModel):
    """The Supervisor's decision after every step."""

    next_agent: Literal["data_cleaning", "data_analyst", "visualization", "research", "report_email", "FINISH"]
    reason: str = Field(description="One short sentence explaining the choice.")
    direct_reply: Optional[str] = Field(
        default=None,
        description="Only when next_agent is FINISH and no specialist was needed "
        "(greeting, clarification, question about the assistant itself).",
    )


CleaningOp = Literal["remove_duplicates", "fill_missing", "drop_missing_rows", "convert_type", "remove_invalid"]


class CleaningFix(BaseModel):
    op: CleaningOp
    column: Optional[str] = Field(default=None, description="Target column (not used by remove_duplicates).")
    strategy: Optional[Literal["median", "mean", "mode", "zero", "constant"]] = Field(
        default=None, description="Only for fill_missing."
    )
    target_type: Optional[Literal["date", "number"]] = Field(default=None, description="Only for convert_type.")
    reason: str = Field(description="One business-language sentence explaining why this fix is useful.")


class CleaningProposal(BaseModel):
    fixes: list[CleaningFix]


class ChartSpec(BaseModel):
    chart_type: Literal["line", "bar", "grouped_bar", "scatter", "pie"]
    x: str
    y: str
    color: Optional[str] = None
    title: str


class EmailBody(BaseModel):
    subject: str
    body: str


class ReportContent(BaseModel):
    executive_summary: str = Field(description="Two or three sentences, main finding first.")
    key_findings: list[str] = Field(description="3 to 5 short findings that restate numbers from the data.")
    limitations: str = Field(description="One or two sentences on what the analysis cannot show.")
