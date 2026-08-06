"""Planner Agent entry point.

The only object anything should use to turn a ``PlannerInput`` into a
``PlannerOutput`` — never the prompt templates, parser, or validator
directly. Understands a user request and produces an ``ExecutionPlan``;
never executes anything. ``PlanningService``/``OrchestrationService``
(elsewhere) are what actually run the plan this returns.

``memory_service`` is an optional collaborator (mirroring every other
optional-collaborator pattern in this codebase). Only this class calls
``MemoryService`` — never ``PlannerAgent``/``PlannerAgentService``,
which stay completely unchanged — so previous plans/reports/executions/
preferences/datasets are folded into the *existing*
``conversation_summary`` prompt block (never a new template
placeholder, which would be a breaking change to every prompt category
sharing one base template) before the AI call, and one DECISION memory
is remembered after a plan is successfully produced.

``adaptive_planning_service`` (Phase 32) is the same kind of optional
collaborator: when present, the freshly-built (but not yet validated)
``execution_plan`` is run through ``AdaptivePlanningService.optimize()``
before validation, so the validator checks the *optimized* plan.
``PlannerAgent``/``PlannerAgentService`` still never see it — Planner
still owns plan generation end to end; adaptive planning only ever
adjusts the plan this method was already going to return.
"""

import json

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.agents.planner.examples.plan_examples import PLAN_EXAMPLES
from backend.agents.planner.exceptions import PlanValidationFailedError
from backend.agents.planner.models.draft import PlannerPlanDraft
from backend.agents.planner.models.io import PlannerInput, PlannerOutput
from backend.agents.planner.parser.plan_parser import PlanParser
from backend.agents.planner.prompts.templates import (
    prompt_name_for_category,
    register_planner_prompts,
    select_category,
)
from backend.agents.planner.validation.plan_validator import PlannerPlanValidator
from backend.ai.models.requests import AIRequest
from backend.ai.prompts.manager import PromptManager
from backend.ingestion.models.dataset import BusinessDataset
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.services.ai_service import AIService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class PlannerService:
    """Generates ``ExecutionPlan``s from natural-language requests. Never executes them."""

    def __init__(
        self,
        ai_service: AIService,
        prompt_manager: PromptManager,
        parser: PlanParser | None = None,
        validator: PlannerPlanValidator | None = None,
        memory_service: MemoryService | None = None,
        adaptive_planning_service: AdaptivePlanningService | None = None,
    ) -> None:
        self._ai_service = ai_service
        self._prompt_manager = prompt_manager
        self._parser = parser or PlanParser()
        self._validator = validator or PlannerPlanValidator()
        self._memory_service = memory_service
        self._adaptive_planning_service = adaptive_planning_service
        register_planner_prompts(self._prompt_manager)

    async def plan(self, planner_input: PlannerInput) -> PlannerOutput:
        """Understand ``planner_input`` and produce a validated ``PlannerOutput``.

        Raises ``MalformedPlanError`` (via the parser) if the model's
        response isn't parseable JSON matching the expected schema, or
        ``PlanValidationFailedError`` if the resulting plan references
        unknown services or has invalid dependencies/ordering. Low
        confidence is never a hard failure — it's surfaced as a warning.
        """
        prompt = self._build_prompt(planner_input)
        response = await self._ai_service.generate(AIRequest(prompt=prompt))

        draft = self._parser.parse(response.content)
        execution_plan = self._build_execution_plan(draft, planner_input)
        execution_plan, optimization_notices = self._optimize_plan(execution_plan, planner_input)

        validation_result = self._validator.validate(
            execution_plan, set(planner_input.available_services), draft.confidence
        )
        if not validation_result.is_valid:
            raise PlanValidationFailedError(
                f"Generated plan failed validation for session '{planner_input.session_id}'.",
                detail=validation_result,
            )

        output = PlannerOutput(
            goal=draft.goal,
            reasoning_summary=draft.reasoning_summary,
            execution_plan=execution_plan,
            confidence=draft.confidence,
            warnings=[
                *draft.warnings, *(issue.message for issue in validation_result.warnings), *optimization_notices
            ],
            assumptions=draft.assumptions,
            estimated_complexity=draft.estimated_complexity,
            estimated_duration=draft.estimated_duration,
        )
        self._remember_decision(output, planner_input)
        return output

    def _optimize_plan(
        self, execution_plan: ExecutionPlan, planner_input: PlannerInput
    ) -> tuple[ExecutionPlan, list[str]]:
        """Run the freshly-built plan through AdaptivePlanningService, if one is wired in.

        Read-only from the Planner's own perspective: this either returns
        ``execution_plan`` unchanged, or a plan
        ``AdaptivePlanningService`` itself decided was safe to mutate
        (see its own ``optimizer/`` package) — Planner never inspects or
        second-guesses the change itself.
        """
        if self._adaptive_planning_service is None:
            return execution_plan, []
        result = self._adaptive_planning_service.optimize(execution_plan, planner_input.session_id)
        notices = [f"Adaptive planning: {decision.message}" for decision in result.decisions]
        return result.optimized_plan, notices

    def _build_prompt(self, planner_input: PlannerInput) -> str:
        category = select_category(planner_input.user_request)
        prompt_name = prompt_name_for_category(category)
        example_json = json.dumps(PLAN_EXAMPLES[category], indent=2)

        conversation_summary = planner_input.conversation_summary or "None."
        memory_context = self._recall_memory_context(planner_input)
        if memory_context:
            conversation_summary = f"{conversation_summary}\n{memory_context}"

        return self._prompt_manager.get(
            prompt_name,
            available_services=self._describe_services(planner_input),
            datasets_summary=self._summarize_datasets(planner_input.uploaded_datasets),
            conversation_summary=conversation_summary,
            sql_connections_summary=", ".join(planner_input.available_sql_connections) or "None declared.",
            browser_context_summary=", ".join(planner_input.available_browser_context) or "None declared.",
            existing_reports_summary=", ".join(planner_input.existing_reports) or "None.",
            example_json=example_json,
            user_request=planner_input.user_request,
        )

    def _recall_memory_context(self, planner_input: PlannerInput) -> str:
        """Fold previous plans/reports/executions/reflections/preferences/datasets into one block.

        Read-only, additive to whatever the caller already declared
        (``conversation_summary``/``existing_reports``) — memory only
        ever supplements, never overrides, what the request already
        carries. Recent reflections (Phase 31 — ``MemoryType.REFLECTION``)
        are folded in exactly like every other memory type here: no
        Planner rewrite, just one more entry in this same loop.
        """
        if self._memory_service is None:
            return ""
        lines: list[str] = []
        for memory_type, label in (
            (MemoryType.DECISION, "Previous plans"),
            (MemoryType.REPORT, "Previous reports"),
            (MemoryType.EXECUTION, "Recent executions"),
            (MemoryType.REFLECTION, "Recent reflections"),
            (MemoryType.DATASET, "Previously used datasets"),
        ):
            result = self._memory_service.search(MemoryQuery(memory_type=memory_type, top_k=3))
            if result.items:
                lines.append(f"{label}: " + "; ".join(item.title for item in result.items))

        preferences = self._memory_service.search(
            MemoryQuery(memory_type=MemoryType.USER_PREFERENCE, session_id=planner_input.session_id, top_k=1)
        )
        if preferences.items:
            lines.append(f"User preferences: {preferences.items[0].content}")

        return "\n".join(lines)

    def _remember_decision(self, output: PlannerOutput, planner_input: PlannerInput) -> None:
        if self._memory_service is None:
            return
        self._memory_service.remember(
            title=f"Plan: {output.goal[:60]}",
            summary=output.reasoning_summary[:300],
            memory_type=MemoryType.DECISION,
            scope=MemoryScope.SESSION,
            content={
                "plan_id": output.execution_plan.plan_id,
                "goal": output.goal,
                "confidence": output.confidence,
                "estimated_complexity": output.estimated_complexity.value,
            },
            importance=output.confidence,
            tags=["plan"],
            metadata={"session_id": planner_input.session_id},
        )

    def _describe_services(self, planner_input: PlannerInput) -> str:
        if not planner_input.available_services:
            return "none declared"
        descriptions = planner_input.available_service_descriptions
        return "; ".join(
            f"{name} ({descriptions[name]})" if name in descriptions else name
            for name in planner_input.available_services
        )

    def _summarize_datasets(self, datasets: list[BusinessDataset]) -> str:
        if not datasets:
            return "None uploaded."
        return "; ".join(
            f"{dataset.dataset_name} ({dataset.row_count} rows, columns: {', '.join(dataset.schema)})"
            for dataset in datasets
        )

    def _build_execution_plan(self, draft: PlannerPlanDraft, planner_input: PlannerInput) -> ExecutionPlan:
        now = utc_now()
        steps = [
            ExecutionStep(
                step_id=step.step_id,
                name=step.name,
                description=step.description,
                node_name=step.node_name,
                dependencies=step.dependencies,
                inputs=step.inputs,
            )
            for step in draft.steps
        ]
        return ExecutionPlan(
            plan_id=generate_id(),
            session_id=planner_input.session_id,
            user_request=planner_input.user_request,
            goal=draft.goal,
            status=PlanStatus.DRAFT,
            confidence=draft.confidence,
            estimated_duration=draft.estimated_duration,
            steps=steps,
            metadata={"generated_by": "planner_service"},
            created_at=now,
            updated_at=now,
        )
