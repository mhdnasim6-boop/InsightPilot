"""Validates a Planner-generated ExecutionPlan.

Reuses ``backend.planning.validator.validator.PlanValidator`` (unknown
nodes, missing/cyclic dependencies, execution order) rather than
reimplementing structural checks, and adds one Planner-specific rule:
confidence below a configurable threshold.
"""
