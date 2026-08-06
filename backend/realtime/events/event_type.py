"""EventType: the closed set of 24 realtime event names this phase supports.

Deliberately its own enum, distinct from ``backend.planning.events.events``'
own ``StepStarted``/``StepCompleted`` (those are transient, in-process
planning-layer signals for the *older* sequential engine — see that
module's own docstring) — this phase's own vocabulary is for the *new*
transport layer and every subsystem it observes, not just planning.
"""

from enum import Enum


class EventType(str, Enum):
    """Every realtime event this phase's transport layer can carry."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    AI_CALL_STARTED = "ai_call_started"
    AI_CALL_COMPLETED = "ai_call_completed"

    MEMORY_STORED = "memory_stored"

    REFLECTION_GENERATED = "reflection_generated"
    OPTIMIZATION_GENERATED = "optimization_generated"

    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"

    USER_LOGGED_IN = "user_logged_in"
    USER_LOGGED_OUT = "user_logged_out"
