"""Dependency-aware, parallel DAG execution engine for ExecutionPlans.

An additive execution path alongside ``backend.planning.executor.PlanExecutor``
— not a replacement. ``PlanExecutor`` still replays the full orchestration
graph once per step (unchanged, still backing ``/planner/execute`` and
every existing HITL test); ``ExecutionService`` (``backend.execution.services``)
instead dispatches each step directly to its own agent service, running
independent steps concurrently via ``asyncio.TaskGroup``, reusing
``ApprovalService``/``ObservabilityService``/``ToolRegistry`` exactly as
they exist today.
"""
