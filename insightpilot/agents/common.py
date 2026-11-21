"""Small helpers shared by the agents."""
from __future__ import annotations

import datetime as dt
import json

from langchain_core.messages import HumanMessage

from ..data.store import DatasetStore
from ..providers.base import message_text


def latest_user_question(state: dict) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return message_text(m.content).strip()
    return ""


def audit(agent: str, status: str = "ok", detail: str = "") -> dict:
    return {"agent": agent, "status": status, "detail": detail[:300], "ts": dt.datetime.now().isoformat(timespec="seconds")}


def ran(state: dict, name: str) -> list[str]:
    """The `agents_run` list for this turn with `name` appended."""
    return list(state.get("agents_run", [])) + [name]


def dataset_brief(store: DatasetStore, dataset_id: str) -> str:
    s = store.schema(dataset_id)
    parts = []
    for c in s["columns"]:
        eg = f", e.g. {', '.join(str(x) for x in c['sample'][:2])}" if c["sample"] else ""
        parts.append(f"{c['name']} ({c['type']}{eg})")
    return f"Table `data` with {s['rows']:,} rows. Columns: " + "; ".join(parts)


def json_default(o):
    return str(o)


def dumps(obj) -> str:
    return json.dumps(obj, default=json_default)
