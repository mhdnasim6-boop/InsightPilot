"""The shared LangGraph state.

Every agent reads from and writes to this one typed object; agents never call each other.
Keep it small and serialisable: it holds references (dataset_id) and small results, never the
dataframe itself, because the checkpointer saves it after every step.
"""
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # --- conversation (persisted per thread by the checkpointer) ---
    messages: Annotated[list[AnyMessage], add_messages]   # reducer: append, don't replace
    conversation_summary: str
    summarized_upto: int

    # --- inputs for this turn ---
    task: str                 # "chat" or "clean_dataset"
    dataset_id: str
    dataset_cleaned: bool
    dataset_brief: str        # one-paragraph description of the table for prompts

    # --- Supervisor ---
    next_agent: str
    routing_reason: str
    step_count: int
    agents_run: list          # specialists that have run in THIS turn

    # --- Data Cleaning ---
    data_profile: dict
    proposed_fixes: list
    cleaning_log: list

    # --- Data Analyst ---
    analysis_result: dict     # question, sql, columns, rows, row_count, truncated
    analyst_note: str

    # --- Visualization ---
    chart_spec: dict
    visualization: str        # Plotly figure as JSON

    # --- Research ---
    external_evidence: list   # {title, url, publisher, published_date, snippet}
    research_note: str

    # --- Report & Email ---
    report: dict
    email_draft: dict
    approval: dict
    email_status: str         # sent | saved_to_outbox | rejected | failed | needs_recipient
    email_detail: str

    # --- output / bookkeeping ---
    final_answer: str
    errors: Annotated[list, operator.add]   # internal detail only; never shown raw to the user
    audit: Annotated[list, operator.add]    # execution history: which agent ran, outcome, when
