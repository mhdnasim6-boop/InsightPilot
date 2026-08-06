"""planner_optimizer: the one place ExecutionPlan.steps is actually mutated.

Only mechanically *safe* mutations happen here — removing a step nothing
else depends on. Everything else (preferring a different agent, reusing
a prior artifact) stays advisory: turning "FileAgent failed, SQLAgent
usually succeeds" into an automatic node-name swap would require
rewriting that step's `inputs` too (FileAgent needs `dataset_reference`,
SQLAgent needs `connection`/`table_name`/`query` — genuinely different
shapes), which is exactly the kind of semantic judgment this phase keeps
out of an automatic mutation.
"""

from backend.adaptive.models.optimization_result import (
    OptimizationDecision,
    OptimizationDecisionCategory,
)
from backend.adaptive.models.planning_context import PlanningContext
from backend.planning.models.plan import ExecutionPlan
from backend.utils.ids import generate_id

PATTERN_THRESHOLD = 2


def build_decision(
    category: OptimizationDecisionCategory, applied: bool, message: str, reason: str, evidence_count: int = 0
) -> OptimizationDecision:
    """Shared constructor every optimizer module in this package uses."""
    return OptimizationDecision(
        decision_id=generate_id(), category=category, applied=applied, message=message, reason=reason,
        evidence_count=evidence_count,
    )


def optimize_plan_steps(plan: ExecutionPlan, context: PlanningContext) -> tuple[ExecutionPlan, list[OptimizationDecision]]:
    """Skip a historically-unnecessary BrowserAgent step (if safe), plus advisory tool-choice/reuse decisions."""
    decisions: list[OptimizationDecision] = []
    steps = list(plan.steps)

    browser_skip_count = context.reflection_patterns.get("browser_skip_count", 0)
    if browser_skip_count >= PATTERN_THRESHOLD:
        depended_on_ids = {dependency for step in steps for dependency in step.dependencies}
        removable = [
            step for step in steps if step.node_name == "browser_agent" and step.step_id not in depended_on_ids
        ]
        for step in removable:
            steps = [s for s in steps if s.step_id != step.step_id]
            decisions.append(
                build_decision(
                    OptimizationDecisionCategory.SKIP_STEP,
                    True,
                    f"Skipped BrowserAgent step '{step.step_id}' — historically unnecessary.",
                    f"BrowserAgent was flagged as unnecessary in {browser_skip_count} prior reflection(s), and "
                    "nothing in this plan depends on its output.",
                    browser_skip_count,
                )
            )

    file_agent_failures = context.reflection_patterns.get("file_agent_failure_count", 0)
    sql_successes = context.reflection_patterns.get("sql_success_count", 0)
    has_file_agent_step = any(step.node_name == "file_agent" for step in steps)
    if has_file_agent_step and file_agent_failures >= PATTERN_THRESHOLD and sql_successes >= PATTERN_THRESHOLD:
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.TOOL_CHOICE,
                False,
                "Consider using SQLAgent instead of FileAgent for this data source.",
                f"FileAgent failed in {file_agent_failures} prior execution(s) while SQLAgent succeeded in "
                f"{sql_successes} prior execution(s).",
                file_agent_failures + sql_successes,
            )
        )

    reused_datasets = context.tool_patterns.get("reused_dataset_count", 0)
    if reused_datasets >= PATTERN_THRESHOLD:
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.REUSE_ARTIFACT,
                False,
                "Consider reusing a previously ingested dataset instead of re-uploading.",
                f"{reused_datasets} relevant dataset memories already exist.",
                reused_datasets,
            )
        )

    reused_reports = context.tool_patterns.get("reused_report_count", 0)
    if reused_reports >= PATTERN_THRESHOLD:
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.REUSE_ARTIFACT,
                False,
                "Consider reusing a previously generated report instead of rebuilding it.",
                f"{reused_reports} relevant report memories already exist.",
                reused_reports,
            )
        )

    reused_visualizations = context.tool_patterns.get("reused_visualization_count", 0)
    if reused_visualizations >= PATTERN_THRESHOLD:
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.REUSE_ARTIFACT,
                False,
                "Consider reusing a previously generated visualization instead of rebuilding it.",
                f"{reused_visualizations} relevant visualization memories already exist.",
                reused_visualizations,
            )
        )

    updated_plan = plan.model_copy(update={"steps": steps}) if len(steps) != len(plan.steps) else plan
    return updated_plan, decisions
