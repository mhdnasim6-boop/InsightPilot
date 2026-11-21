"""Application runtime: owns the provider, dataset store, graph and conversation memory.

The Streamlit UI (and the tests) talk only to `InsightPilotApp`; nothing here imports Streamlit.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .config import Settings, get_settings
from .data.store import DatasetError, DatasetStore
from .graph.workflow import build_graph
from .providers.base import AIProvider, ProviderUnavailable, StructuredOutputError
from .providers.factory import get_provider

# Per-turn fields are reset at the start of every user question; the conversation itself persists.
TURN_RESET = dict(step_count=0, agents_run=[], next_agent="", routing_reason="", analysis_result={}, analyst_note="",
                  chart_spec={}, visualization="", external_evidence=[], research_note="", report={}, email_draft={},
                  email_status="", email_detail="", approval={}, final_answer="", proposed_fixes=[], task="chat")


def friendly_error(exc: BaseException, provider: AIProvider) -> str:
    if isinstance(exc, ProviderUnavailable):
        if provider.name == "ollama":
            return ("I can't reach the local Ollama model. Start Ollama and pull the model "
                    "(`ollama pull qwen2.5:3b`), or switch LLM_PROVIDER to openai in your .env file.")
        return "I can't reach the OpenAI service. Check OPENAI_API_KEY and your network connection."
    if isinstance(exc, StructuredOutputError):
        return "The AI model returned an answer I couldn't use. Please try again or rephrase your question."
    if isinstance(exc, DatasetError):
        return str(exc)
    return "Something went wrong while processing that request. Please try again."


class InsightPilotApp:
    def __init__(self, settings: Settings | None = None, provider: AIProvider | None = None,
                 store: DatasetStore | None = None, search_fn=None, checkpoint_path: Path | None = None):
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(settings=self.settings)
        self.store = store or DatasetStore(self.settings)
        base = Path(self.settings.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(checkpoint_path or base / "checkpoints.sqlite"), check_same_thread=False)
        self.checkpointer = SqliteSaver(self._conn)
        self.graph = build_graph(self.provider, self.store, self.settings, self.checkpointer, search_fn)
        self._conv = sqlite3.connect(str(base / "conversations.sqlite"), check_same_thread=False)
        self._conv.execute("CREATE TABLE IF NOT EXISTS conversations (thread_id TEXT PRIMARY KEY, dataset_id TEXT, title TEXT, created TEXT)")
        self._conv.commit()

    # ---- datasets ---------------------------------------------------------
    def upload_dataset(self, filename: str, content: bytes) -> str:
        return self.store.create_dataset(filename, content)

    # ---- conversations ----------------------------------------------------
    def new_conversation(self, dataset_id: str, title: str = "New conversation") -> str:
        tid = uuid.uuid4().hex[:12]
        self._conv.execute("INSERT INTO conversations VALUES (?,?,?,?)", (tid, dataset_id, title, dt.datetime.now().isoformat(timespec="seconds")))
        self._conv.commit()
        return tid

    def list_conversations(self, dataset_id: str | None = None) -> list[dict]:
        q, args = "SELECT thread_id, dataset_id, title, created FROM conversations", ()
        if dataset_id:
            q, args = q + " WHERE dataset_id=?", (dataset_id,)
        rows = self._conv.execute(q + " ORDER BY created DESC", args).fetchall()
        return [dict(zip(("thread_id", "dataset_id", "title", "created"), r)) for r in rows]

    def _title_if_new(self, thread_id: str, question: str) -> None:
        self._conv.execute("UPDATE conversations SET title=? WHERE thread_id=? AND title='New conversation'", (question[:50], thread_id))
        self._conv.commit()

    def history(self, thread_id: str) -> list[dict]:
        snap = self.graph.get_state(self._cfg(thread_id))
        out = []
        for m in (snap.values or {}).get("messages", []):
            if m.type in ("human", "ai") and isinstance(m.content, str) and m.content.strip():
                out.append({"role": "user" if m.type == "human" else "assistant", "content": m.content})
        return out

    # ---- running the graph --------------------------------------------------
    def _cfg(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": self.settings.recursion_limit}

    def _base_input(self, dataset_id: str) -> dict:
        meta = self.store.meta(dataset_id)
        return {**TURN_RESET, "dataset_id": dataset_id,
                "dataset_cleaned": bool(meta.get("cleaned") or meta.get("cleaning_reviewed")),
                "dataset_brief": ""}

    def _finish(self, thread_id: str) -> dict:
        """Package the graph's current state for the UI: either an answer, or a pending approval."""
        snap = self.graph.get_state(self._cfg(thread_id))
        v = snap.values or {}
        pending = [i for t in snap.tasks for i in t.interrupts]
        if pending:
            return {"status": "interrupted", "interrupt": pending[0].value, "thread_id": thread_id, "audit": v.get("audit", [])}
        return {"status": "done", "thread_id": thread_id, "answer": v.get("final_answer", ""),
                "visualization": v.get("visualization", ""), "analysis_result": v.get("analysis_result", {}),
                "report": v.get("report", {}), "external_evidence": v.get("external_evidence", []),
                "email_status": v.get("email_status", ""), "cleaning_log": v.get("cleaning_log", []),
                "audit": v.get("audit", [])}

    def _run(self, thread_id: str, payload) -> dict:
        try:
            self.graph.invoke(payload, self._cfg(thread_id))
            return self._finish(thread_id)
        except Exception as exc:  # noqa: BLE001 - the UI shows a friendly message, never a traceback
            return {"status": "error", "thread_id": thread_id, "error": friendly_error(exc, self.provider), "detail": repr(exc)}

    def ask(self, thread_id: str, dataset_id: str, question: str) -> dict:
        self._title_if_new(thread_id, question)
        return self._run(thread_id, {**self._base_input(dataset_id), "messages": [HumanMessage(content=question)]})

    def start_cleaning(self, thread_id: str, dataset_id: str) -> dict:
        return self._run(thread_id, {**self._base_input(dataset_id), "task": "clean_dataset", "dataset_cleaned": False})

    def resume(self, thread_id: str, decision: dict) -> dict:
        """Answer a pending approval. Cleaning: {"approved_ids": [...]}. Email: {"approved": bool, "subject":..., "body":...}."""
        return self._run(thread_id, Command(resume=decision))

    def pending_interrupt(self, thread_id: str) -> dict | None:
        snap = self.graph.get_state(self._cfg(thread_id))
        pending = [i for t in snap.tasks for i in t.interrupts]
        return pending[0].value if pending else None

    def close(self) -> None:
        self._conn.close()
        self._conv.close()
