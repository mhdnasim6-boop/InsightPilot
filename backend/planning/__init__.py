"""Reusable planning subsystem: represents execution as structured, inspectable plans.

Strictly separated from ``backend.orchestration``: a future Planner agent
only ever produces an ``ExecutionPlan``; ``PlanExecutor`` is the only thing
that turns a plan into orchestration runs, via
``backend.services.orchestration_service.OrchestrationService``. No AI
reasoning, business agent, or prompt lives in this package — only the
models, validation, optimization, execution-delegation, and visualization
infrastructure a future Planner will sit on top of.
"""
