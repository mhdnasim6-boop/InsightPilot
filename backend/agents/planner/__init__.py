"""The Planner Agent: understands a user request and produces an ``ExecutionPlan``.

Never executes anything — ``backend.services.planner_service.PlannerService``
is the only entry point, and it only ever returns a ``PlannerOutput``
wrapping a plan for something else (``PlanningService``, then
``OrchestrationService``) to run.
"""
