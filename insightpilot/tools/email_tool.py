"""Sending email. Only ever called from the `send_email` graph node, which is reachable only after approval.

If SMTP is not configured, the approved message is written to data/outbox/ as an .eml file and the
status says so plainly (`saved_to_outbox`); the system never claims to have sent something it did not.
"""
from __future__ import annotations

import re
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path

from ..config import Settings

_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}$")
EMAIL_IN_TEXT = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def valid_email(addr: str) -> bool:
    return bool(addr and _EMAIL.match(addr.strip()))


def find_email(text: str) -> str | None:
    m = EMAIL_IN_TEXT.search(text or "")
    return m.group(0) if m else None


def send_email(to: str, subject: str, body: str, attachment: str | None, settings: Settings) -> dict:
    """Returns {"status": "sent" | "saved_to_outbox" | "failed", "detail": str}."""
    if not valid_email(to):
        return {"status": "failed", "detail": "The recipient address is not valid."}
    msg = EmailMessage()
    msg["To"], msg["Subject"] = to.strip(), subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "insightpilot@localhost"
    msg.set_content(body)
    if attachment and Path(attachment).is_file():
        msg.add_attachment(Path(attachment).read_bytes(), maintype="application", subtype="pdf",
                           filename=Path(attachment).name)
    if not settings.smtp_host:
        outbox = Path(settings.data_dir) / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        f = outbox / f"{uuid.uuid4().hex[:8]}.eml"
        f.write_bytes(bytes(msg))
        return {"status": "saved_to_outbox", "detail": str(f)}
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return {"status": "sent", "detail": f"Sent to {to.strip()}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "detail": str(exc)[:200]}
