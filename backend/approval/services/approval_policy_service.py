"""ApprovalPolicyService: the one place the currently active ApprovalPolicy is held.

A single mutable "current policy" (default NEVER — HITL is opt-in, not
a silent behavior change for existing callers), configurable via
``set_policy()``. Mirrors ``ToolRegistry``'s own "process-wide, mutated
through a single well-known service" shape from Phase 22.
"""

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType


class ApprovalPolicyService:
    """Holds and evaluates the process-wide active ApprovalPolicy."""

    def __init__(self, policy: ApprovalPolicy | None = None) -> None:
        self._policy = policy or ApprovalPolicy(policy_type=ApprovalPolicyType.NEVER)

    def get_policy(self) -> ApprovalPolicy:
        """Return the currently active policy."""
        return self._policy

    def set_policy(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        """Replace the currently active policy and return it."""
        self._policy = policy
        return self._policy

    def requires_approval(self, node_name: str) -> bool:
        """Return whether the active policy requires approval before ``node_name`` runs."""
        return self._policy.requires_approval(node_name)
