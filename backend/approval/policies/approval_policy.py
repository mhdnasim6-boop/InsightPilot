"""ApprovalPolicy: decides, per graph node, whether a human must approve before it runs.

One active policy at a time (configurable via ``ApprovalPolicyService``)
rather than per-node overrides — matches the six named strategies this
phase specifies exactly. Policy evaluation is a pure function of a node
name; it never touches the graph, a plan, or a service, so it is trivial
to unit test and safe to call from anywhere (PlanExecutor's step loop,
a REST handler previewing what a plan would pause on, ...).
"""

from enum import Enum

from pydantic import BaseModel

_RISKY_NODE_NAMES = frozenset({"sql_agent", "browser_agent", "report_agent"})


class ApprovalPolicyType(str, Enum):
    """Every supported approval strategy."""

    NEVER = "never"
    ALWAYS = "always"
    ON_RISKY_OPERATIONS = "on_risky_operations"
    ON_SQL = "on_sql"
    ON_BROWSER = "on_browser"
    ON_REPORT_PUBLISHING = "on_report_publishing"


class ApprovalPolicy(BaseModel):
    """The currently active approval strategy."""

    policy_type: ApprovalPolicyType = ApprovalPolicyType.NEVER

    def requires_approval(self, node_name: str) -> bool:
        """Return whether ``node_name`` (a gated agent, e.g. ``"sql_agent"``) needs approval."""
        if self.policy_type == ApprovalPolicyType.NEVER:
            return False
        if self.policy_type == ApprovalPolicyType.ALWAYS:
            return True
        if self.policy_type == ApprovalPolicyType.ON_RISKY_OPERATIONS:
            return node_name in _RISKY_NODE_NAMES
        if self.policy_type == ApprovalPolicyType.ON_SQL:
            return node_name == "sql_agent"
        if self.policy_type == ApprovalPolicyType.ON_BROWSER:
            return node_name == "browser_agent"
        if self.policy_type == ApprovalPolicyType.ON_REPORT_PUBLISHING:
            return node_name == "report_agent"
        return False
