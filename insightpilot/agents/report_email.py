"""Report & Email Agent (+ its Human-in-the-Loop send approval).

  report_email    writes a PDF report from the verified SQL result and, if asked, DRAFTS an email. Sends nothing.
  email_approval  pauses with interrupt(); the email is sent only if the user approves (they may edit it first).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from ..config import Settings
from ..data.store import DatasetStore
from ..providers.base import AIProvider, StructuredOutputError
from ..schemas import EmailBody, ReportContent
from ..tools.email_tool import find_email, send_email, valid_email
from ..tools.report_tool import generate_report_pdf
from .common import audit, latest_user_question, ran

REPORT_PROMPT = """You are the Report agent. Write report text for a business reader from the verified result table.
Use ONLY numbers that appear in the table; never invent figures. Main finding first. External context is possible
background only: say 'may be related', never 'caused by'. State one limitation (e.g. correlation is not cause)."""
EMAIL_PROMPT = """Write a short professional email (subject + body, under 120 words) sharing the attached report.
State the main finding in one sentence using only the provided summary. Do not add numbers that are not in it."""


def wants_email(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in ("email", "e-mail", "mail it", "mail this", "send it", "send this", "send the report", "send to"))


def _fallback_content(res: dict) -> ReportContent:
    cols, rows = res.get("columns", []), res.get("rows", [])
    findings = [", ".join(f"{c}: {v}" for c, v in zip(cols, r)) for r in rows[:4]]
    return ReportContent(executive_summary=f"Analysis of: {res.get('question', 'the dataset')}. The key figures are listed below.",
                         key_findings=findings,
                         limitations="Figures are calculated directly from the dataset; they describe what happened, not why.")


def make_report_email(provider: AIProvider, store: DatasetStore, settings: Settings):
    def report_email(state: dict) -> dict:
        res = state.get("analysis_result") or {}
        question = latest_user_question(state)
        dataset_id = state["dataset_id"]
        name = store.meta(dataset_id).get("filename", dataset_id)
        update: dict = {"agents_run": ran(state, "report_email")}
        evidence = state.get("external_evidence") or []
        try:
            content = provider.structured(
                [SystemMessage(content=REPORT_PROMPT),
                 HumanMessage(content=f"Question: {question}\nColumns: {res.get('columns')}\nRows: {res.get('rows', [])[:15]}\n"
                                      f"Analyst note: {state.get('analyst_note', '')}\n"
                                      f"External context: {state.get('research_note', '') or 'none'}")],
                ReportContent)
        except StructuredOutputError as exc:
            content = _fallback_content(res)
            update["errors"] = [f"report: used fallback text ({exc})"]
        path = Path(settings.data_dir) / "reports" / dataset_id / f"report_{dt.datetime.now():%Y%m%d_%H%M%S}.pdf"
        generate_report_pdf(path, title="InsightPilot Business Report", dataset_name=name,
                            executive_summary=content.executive_summary, key_findings=content.key_findings,
                            columns=res.get("columns", []), rows=res.get("rows", []), sql=res.get("sql", ""),
                            evidence=evidence, limitations=content.limitations)
        update["report"] = {"path": str(path), "executive_summary": content.executive_summary,
                            "key_findings": content.key_findings, "limitations": content.limitations}
        update["audit"] = [audit("report_email", "ok", f"report {path.name}")]
        if not wants_email(question):
            return update
        to = find_email(question)
        if not to:
            update.update(email_status="needs_recipient",
                          email_detail="Tell me the recipient's email address (for example: 'email it to name@company.com').")
            return update
        try:
            mail = provider.structured(
                [SystemMessage(content=EMAIL_PROMPT),
                 HumanMessage(content=f"Report summary: {content.executive_summary}\nKey findings: {content.key_findings}")],
                EmailBody)
        except StructuredOutputError:
            mail = EmailBody(subject="InsightPilot business report",
                             body=f"Hello,\n\nPlease find the report attached.\n\n{content.executive_summary}\n\nRegards")
        update["email_draft"] = {"to": to, "subject": mail.subject, "body": mail.body, "attachment": str(path)}
        return update

    return report_email


def route_after_report(state: dict) -> str:
    return "email_approval" if state.get("email_draft") and not state.get("email_status") else "supervisor"


def make_email_approval(settings: Settings):
    def email_approval(state: dict) -> dict:
        draft = state["email_draft"]
        # Human-in-the-Loop: nothing is sent until the user answers this interrupt.
        decision = interrupt({"type": "send_email", "draft": draft})
        decision = decision if isinstance(decision, dict) else {}
        if not decision.get("approved"):
            return {"email_status": "rejected", "email_detail": "The email was not sent.", "approval": {"email": False},
                    "audit": [audit("email_approval", "rejected", draft["to"])]}
        to = decision.get("to") or draft["to"]
        if not valid_email(to):
            return {"email_status": "failed", "email_detail": "The recipient address is not valid.",
                    "audit": [audit("email_approval", "failed", "invalid recipient")]}
        out = send_email(to, decision.get("subject") or draft["subject"], decision.get("body") or draft["body"],
                         draft.get("attachment"), settings)
        return {"email_status": out["status"], "email_detail": out["detail"], "approval": {"email": True},
                "audit": [audit("email_approval", out["status"], out["detail"])]}

    return email_approval
