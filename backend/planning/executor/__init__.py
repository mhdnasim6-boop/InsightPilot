"""Converts a validated, optimized ExecutionPlan into orchestration runs.

``PlanExecutor`` is the only bridge between planning and orchestration —
it delegates every step to ``OrchestrationService``, tracking plan/step
progress and emitting planning events. It implements no business logic:
what a step actually does is entirely up to whatever graph
``OrchestrationService`` currently runs.
"""
