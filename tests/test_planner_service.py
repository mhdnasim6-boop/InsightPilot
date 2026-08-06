"""Integration tests for PlannerService, using ONLY the real MockProvider — no external LLM.

MockProvider deterministically echoes its prompt back. Because the
planner prompt template embeds a concrete, valid worked-example plan as
few-shot guidance, the echoed response legitimately contains parseable
JSON — so these tests exercise the full prompt -> AIService -> parse ->
validate pipeline against the real, unmodified MockProvider.
"""

import asyncio

import pytest

from backend.agents.planner.exceptions import (
    MalformedPlanError,
    PlanValidationFailedError,
)
from backend.agents.planner.models.io import PlannerInput
from backend.agents.planner.parser.plan_parser import PlanParser
from backend.agents.planner.prompts.templates import PROMPT_NAMES
from backend.agents.planner.validation.plan_validator import PlannerPlanValidator
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.planning.models.enums import PlanStatus
from backend.services.ai_service import AIService
from backend.services.planner_service import PlannerService
from config.settings import Settings


def _make_service(**overrides: object) -> PlannerService:
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    prompt_manager = PromptManager()
    return PlannerService(ai_service, prompt_manager, **overrides)  # type: ignore[arg-type]


_ALL_AGENT_NAMES = {"file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"}


@pytest.mark.parametrize(
    "user_request",
    [
        "Analyze uploaded sales file.",
        "Analyze customer table from SQL.",
        "Generate a business report.",
        "Compare uploaded CSV with SQL sales table.",
        "Generate report with recent market context.",
        "Give me business recommendations from the report.",
        "Please clean my uploaded customer records dataset.",
    ],
)
def test_plan_succeeds_for_every_prompt_category(user_request: str) -> None:
    async def scenario() -> None:
        service = _make_service()
        planner_input = PlannerInput(
            user_request=user_request,
            session_id="sess-1",
            available_services=list(_ALL_AGENT_NAMES),
        )

        output = await service.plan(planner_input)

        assert output.goal
        assert output.reasoning_summary
        assert 0.0 <= output.confidence <= 1.0
        assert output.execution_plan.status == PlanStatus.DRAFT
        assert output.execution_plan.session_id == "sess-1"
        assert output.execution_plan.user_request == user_request
        assert output.execution_plan.confidence == output.confidence
        assert len(output.execution_plan.steps) > 0
        assert all(step.node_name in _ALL_AGENT_NAMES for step in output.execution_plan.steps)

    asyncio.run(scenario())


def test_plan_raises_plan_validation_failed_for_a_hallucinated_node() -> None:
    async def scenario() -> None:
        service = _make_service()
        # "file_agent" is deliberately left out of available_services, but the
        # matched example plan references it -> unknown_node_name failure.
        planner_input = PlannerInput(
            user_request="Please clean my uploaded customer records dataset.",
            available_services=["executive_summary_agent"],
        )

        with pytest.raises(PlanValidationFailedError) as exc_info:
            await service.plan(planner_input)

        assert any(issue.code == "unknown_node_name" for issue in exc_info.value.detail.errors)

    asyncio.run(scenario())


def test_plan_surfaces_low_confidence_as_a_warning_not_a_failure() -> None:
    async def scenario() -> None:
        # Threshold set above every built-in example's confidence, so this
        # exercises the low_confidence warning path end to end.
        service = _make_service(validator=PlannerPlanValidator(confidence_threshold=0.99))
        planner_input = PlannerInput(
            user_request="Please clean my uploaded customer records dataset.",
            available_services=list(_ALL_AGENT_NAMES),
        )

        output = await service.plan(planner_input)

        assert any("below the recommended threshold" in warning for warning in output.warnings)

    asyncio.run(scenario())


def test_plan_raises_malformed_plan_error_when_the_response_has_no_json() -> None:
    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
        ai_service = AIService(ProviderFactory(settings), settings)
        prompt_manager = PromptManager()
        service = PlannerService(ai_service, prompt_manager)

        # Overwrite one category's registered template (PromptManager.register
        # overwrites) with plain text containing no JSON at all, so
        # MockProvider's echo has nothing parseable in it.
        prompt_manager.register(PROMPT_NAMES["data_cleaning_request"], "Just clean the data, no JSON here.")
        planner_input = PlannerInput(
            user_request="Please clean my dataset.",
            available_services=["ingestion", "cleaning"],
        )

        with pytest.raises(MalformedPlanError):
            await service.plan(planner_input)

    asyncio.run(scenario())


def test_planner_service_accepts_injected_parser_and_validator() -> None:
    parser = PlanParser()
    validator = PlannerPlanValidator(confidence_threshold=0.1)
    service = _make_service(parser=parser, validator=validator)
    assert service is not None  # constructs without error with explicit collaborators
