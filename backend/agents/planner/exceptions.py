"""Planner Agent exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
planner-specific special-casing. Kept as a single flat module (unlike
other layers' ``exceptions/`` packages) since the requested folder list
for this phase didn't include one and the Planner's error surface is
small enough not to need a sub-package.
"""

from backend.core.exceptions import InsightPilotError


class PlannerError(InsightPilotError):
    """Base class for all Planner Agent exceptions."""

    status_code = 500
    error_type = "PlannerError"


class MalformedPlanError(PlannerError):
    """Raised when the model's response isn't parseable JSON matching the expected schema."""

    status_code = 422
    error_type = "MalformedPlanError"


class PlanValidationFailedError(PlannerError):
    """Raised when a generated plan references unknown services or has invalid structure.

    Always carries the triggering ``PlanValidationResult`` as ``detail``.
    """

    status_code = 422
    error_type = "PlanValidationFailedError"


class InvalidPlannerAgentInputError(PlannerError):
    """Raised when the given ExecutionStep/session don't carry what PlannerAgent needs to run.

    Raised immediately, before ``PlannerService`` is called — a malformed
    request (missing ``user_request``), not a legitimate planning
    failure. Contrast with the underlying LLM call/parse/validation
    failing: that is captured in a FAILED ``PlannerAgentResult``, never
    raised, mirroring every other agent's own node.
    """

    status_code = 422
    error_type = "InvalidPlannerAgentInputError"
