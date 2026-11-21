"""Data Cleaning Agent (+ its Human-in-the-Loop approval node).

Two nodes:
  data_cleaning     profiles the data, proposes fixes. Code finds the problems, the LLM reviews them and
                    words each fix in business language; every fix is validated against a fixed menu.
  cleaning_approval pauses the graph with interrupt(); on resume applies ONLY the fixes the user approved.
Nothing in the dataset changes before approval.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from ..config import Settings
from ..data.store import DatasetStore
from ..providers.base import AIProvider, StructuredOutputError
from ..schemas import CleaningProposal
from ..tools.cleaning_tools import apply_fixes, detect_candidate_fixes, finalise_fixes, profile_dataframe
from .common import audit, dataset_brief, ran

CLEANING_PROMPT = """You are the Data Cleaning agent for a business-intelligence tool.
You receive a data-quality profile and a list of candidate fixes found by automatic checks.
Return the fixes worth applying, using ONLY these operations:
remove_duplicates, fill_missing (strategy: median|mean|mode|zero|constant), drop_missing_rows,
convert_type (target_type: date|number), remove_invalid.
Use column names exactly as given. Write each `reason` as one plain business sentence (no jargon).
Do not invent columns and do not propose anything that is not supported by the profile."""


def _key(f: dict) -> tuple:
    return (f["op"], f.get("column"), f.get("target_type"))


def make_data_cleaning(provider: AIProvider, store: DatasetStore, settings: Settings):
    def data_cleaning(state: dict) -> dict:
        dataset_id = state["dataset_id"]
        df = store.load_df(dataset_id)
        profile = profile_dataframe(df)
        candidates = detect_candidate_fixes(df, profile)
        update: dict = {"data_profile": {k: profile[k] for k in ("rows", "duplicate_rows") if k in profile},
                        "agents_run": ran(state, "data_cleaning")}
        proposed = list(candidates)
        if candidates:
            try:
                proposal = provider.structured(
                    [SystemMessage(content=CLEANING_PROMPT),
                     HumanMessage(content="Profile:\n" + json.dumps(profile, default=str)[:3500]
                                  + "\n\nCandidate fixes:\n" + json.dumps(candidates, default=str))],
                    CleaningProposal)
                llm_fixes = [f.model_dump(exclude_none=True) for f in proposal.fixes]
                have = {_key(f) for f in llm_fixes}
                # the LLM may reword and reorder, but it cannot silently drop a problem the checks found
                proposed = llm_fixes + [c for c in candidates if _key(c) not in have]
            except StructuredOutputError as exc:
                update["errors"] = [f"cleaning: used rule-based fixes ({exc})"]
        fixes = finalise_fixes(df, proposed)
        update["proposed_fixes"] = fixes
        if not fixes:
            store.update_meta(dataset_id, cleaned=True, cleaning_reviewed=True)
            update.update(dataset_cleaned=True, cleaning_log=[{"status": "none", "message": "No data-quality issues found."}])
        update["audit"] = [audit("data_cleaning", "ok", f"{len(fixes)} fix(es) proposed")]
        update["dataset_brief"] = dataset_brief(store, dataset_id)
        return update

    return data_cleaning


def route_after_cleaning(state: dict) -> str:
    return "cleaning_approval" if state.get("proposed_fixes") and not state.get("dataset_cleaned") else "supervisor"


def make_cleaning_approval(store: DatasetStore):
    def cleaning_approval(state: dict) -> dict:
        fixes = state.get("proposed_fixes", [])
        # Human-in-the-Loop: the graph stops here and its state is checkpointed until the user answers.
        decision = interrupt({"type": "cleaning_fixes", "dataset_id": state["dataset_id"], "fixes": fixes})
        approved_ids = set(decision.get("approved_ids") or []) if isinstance(decision, dict) else set()
        chosen = [f for f in fixes if f["id"] in approved_ids]
        dataset_id = state["dataset_id"]
        if chosen:
            df, logs = apply_fixes(store.load_df(dataset_id), chosen)
            store.save_current(dataset_id, df)
            store.update_meta(dataset_id, cleaned=True, cleaning_reviewed=True, cleaning_log=logs)
        else:
            logs = [{"status": "rejected", "message": "No fixes were approved; the data was left unchanged."}]
            store.update_meta(dataset_id, cleaning_reviewed=True)
        return {"cleaning_log": logs, "dataset_cleaned": True, "proposed_fixes": [],
                "dataset_brief": dataset_brief(store, dataset_id),
                "approval": {"cleaning": [f["id"] for f in chosen]},
                "audit": [audit("cleaning_approval", "ok", f"{len(chosen)} of {len(fixes)} fixes approved")]}

    return cleaning_approval
