"""Tests for the Planner Agent's models: drafts, ComplexityLevel, PlannerInput/PlannerOutput."""

import pytest
from pydantic import ValidationError

from backend.agents.planner.models.complexity import ComplexityLevel
from backend.agents.planner.models.draft import PlannerPlanDraft, PlannerStepDraft
from backend.agents.planner.models.io import PlannerInput, PlannerOutput
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.utils.time import utc_now


def test_planner_step_draft_defaults() -> None:
    step = PlannerStepDraft(step_id="s1", name="Ingest", node_name="ingestion")
    assert step.description is None
    assert step.dependencies == []


def test_planner_plan_draft_accepts_a_well_formed_payload() -> None:
    draft = PlannerPlanDraft(
        goal="g",
        reasoning_summary="r",
        confidence=0.8,
        estimated_complexity=ComplexityLevel.MEDIUM,
        steps=[PlannerStepDraft(step_id="s1", name="Ingest", node_name="ingestion")],
    )
    assert draft.estimated_complexity == ComplexityLevel.MEDIUM
    assert draft.warnings == []
    assert draft.assumptions == []


def test_planner_plan_draft_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        PlannerPlanDraft(goal="g", reasoning_summary="r", confidence=1.5, estimated_complexity=ComplexityLevel.LOW)


def test_planner_plan_draft_rejects_unknown_complexity() -> None:
    with pytest.raises(ValidationError):
        # Intentionally passing a value outside the ComplexityLevel enum to
        # prove pydantic rejects it — the mismatch with the declared
        # parameter type is the point of this test, not an error.
        PlannerPlanDraft(
            goal="g",
            reasoning_summary="r",
            confidence=0.5,
            estimated_complexity="extreme",  # type: ignore[arg-type]
        )


def test_planner_input_defaults() -> None:
    planner_input = PlannerInput(user_request="hello")
    assert planner_input.session_id is None
    assert planner_input.uploaded_datasets == []
    assert planner_input.available_services == []
    assert planner_input.user_preferences == {}
    assert planner_input.metadata == {}


def test_planner_input_accepts_business_datasets() -> None:
    now = utc_now()
    dataset = BusinessDataset(
        dataset_id="d1",
        dataset_name="sales",
        source_type=SourceType.CSV,
        source_location="/data/sales.csv",
        row_count=10,
        column_count=3,
        created_at=now,
        loaded_at=now,
    )
    planner_input = PlannerInput(user_request="analyze this", uploaded_datasets=[dataset])
    assert planner_input.uploaded_datasets[0].dataset_id == "d1"


def test_planner_output_wraps_a_real_execution_plan() -> None:
    now = utc_now()
    plan = ExecutionPlan(
        plan_id="p1", created_at=now, updated_at=now, status=PlanStatus.DRAFT, steps=[]
    )
    output = PlannerOutput(
        goal="g",
        reasoning_summary="r",
        execution_plan=plan,
        confidence=0.9,
        estimated_complexity=ComplexityLevel.LOW,
    )
    assert output.execution_plan.plan_id == "p1"
    assert output.warnings == []
    assert output.assumptions == []
