"""Parses and structurally validates an LLM's raw planning response."""

from pydantic import ValidationError

from backend.agents.planner.exceptions import MalformedPlanError
from backend.agents.planner.models.draft import PlannerPlanDraft
from backend.agents.planner.parser.json_extractor import extract_json_object


class PlanParser:
    """Converts raw AI-response text into a validated ``PlannerPlanDraft``."""

    def parse(self, content: str) -> PlannerPlanDraft:
        """Extract and validate a ``PlannerPlanDraft`` from raw response text.

        Raises ``MalformedPlanError`` if no JSON object is found, the JSON
        is invalid, or it doesn't match the expected schema (including an
        out-of-vocabulary ``estimated_complexity`` or an out-of-range
        ``confidence``) — pydantic's own validation catches those for us.
        """
        try:
            raw_json = extract_json_object(content)
        except ValueError as exc:
            raise MalformedPlanError(f"No JSON object found in the planner response: {exc}") from exc

        try:
            return PlannerPlanDraft.model_validate_json(raw_json)
        except ValidationError as exc:
            raise MalformedPlanError(f"Planner response did not match the expected schema: {exc}") from exc
