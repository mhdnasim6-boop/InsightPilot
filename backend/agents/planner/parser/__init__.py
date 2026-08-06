"""Converts raw AI-response text into a validated ``PlannerPlanDraft``.

Detects malformed JSON and schema mismatches here, before anything
becomes a real ``ExecutionPlan``.
"""
