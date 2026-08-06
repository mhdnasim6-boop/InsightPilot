"""Workflow Engine: the highest orchestration layer in InsightPilot.

Coordinates every existing subsystem — the Planner Agent, the parallel
DAG execution engine, approvals, memory, observability, reflection,
adaptive planning, tools, plugins, and (at the REST layer) security —
into one autonomous workflow system. Introduces no new business
intelligence logic of its own: ``WorkflowService`` is the single public
entry point, and it delegates every real computation to the existing
service it wraps. See ``backend.workflows.services.workflow_service``
for the full composition.
"""
