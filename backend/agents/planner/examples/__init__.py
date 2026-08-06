"""Concrete worked examples embedded as few-shot guidance in planner prompts.

Each example is a complete, valid ``PlannerPlanDraft``-shaped JSON object —
real enough that even a local/mock provider echoing it back exercises the
full parse path, and detailed enough to guide a real LLM's output format.

Every example deliberately references only services that actually exist
today (``ingestion``, ``cleaning``) — no File/SQL/Analysis/Visualization/
Report agent is implemented yet, so the examples say so honestly in their
own ``warnings`` rather than pretending those steps exist.
"""
