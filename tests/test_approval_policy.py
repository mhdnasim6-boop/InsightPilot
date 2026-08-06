"""Unit tests for ApprovalPolicy: pure node-name -> bool decisions, one per policy type."""

import pytest

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType


@pytest.mark.parametrize("node_name", ["file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"])
def test_never_policy_requires_approval_for_nothing(node_name: str) -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.NEVER)
    assert policy.requires_approval(node_name) is False


@pytest.mark.parametrize("node_name", ["file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"])
def test_always_policy_requires_approval_for_everything(node_name: str) -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.ALWAYS)
    assert policy.requires_approval(node_name) is True


@pytest.mark.parametrize(
    ("node_name", "expected"),
    [
        ("file_agent", False),
        ("sql_agent", True),
        ("browser_agent", True),
        ("report_agent", True),
        ("executive_summary_agent", False),
    ],
)
def test_on_risky_operations_gates_sql_browser_and_report_only(node_name: str, expected: bool) -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.ON_RISKY_OPERATIONS)
    assert policy.requires_approval(node_name) is expected


def test_on_sql_gates_only_sql_agent() -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.ON_SQL)
    assert policy.requires_approval("sql_agent") is True
    for other in ("file_agent", "browser_agent", "report_agent", "executive_summary_agent"):
        assert policy.requires_approval(other) is False


def test_on_browser_gates_only_browser_agent() -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.ON_BROWSER)
    assert policy.requires_approval("browser_agent") is True
    for other in ("file_agent", "sql_agent", "report_agent", "executive_summary_agent"):
        assert policy.requires_approval(other) is False


def test_on_report_publishing_gates_only_report_agent() -> None:
    policy = ApprovalPolicy(policy_type=ApprovalPolicyType.ON_REPORT_PUBLISHING)
    assert policy.requires_approval("report_agent") is True
    for other in ("file_agent", "sql_agent", "browser_agent", "executive_summary_agent"):
        assert policy.requires_approval(other) is False


def test_default_policy_type_is_never() -> None:
    assert ApprovalPolicy().policy_type == ApprovalPolicyType.NEVER
