"""Strongly typed models for execution plans and steps.

``ExecutionPlan``/``ExecutionStep`` describe work to be done; they carry no
orchestration or business logic themselves. See
``backend.planning.executor.executor.PlanExecutor`` for how a plan is
turned into orchestration runs.
"""
