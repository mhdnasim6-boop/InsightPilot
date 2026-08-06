"""Planner Agent providers: parser, validator, planner service, PlannerAgent result store.

``get_planner_agent_result_store`` is deliberately here, not in a new
``dependencies/planner_agent.py``: ``PlannerAgentService``/
``PlannerAgentNode`` themselves are constructed inside
``backend.dependencies.orchestration.get_graph_builder`` (they need a
live ``GraphBuilder`` reference for dynamic agent discovery — see
``backend.agents.planner.execution.planner_agent``), so putting the
store's provider here (which ``orchestration.py`` already depends on for
``get_planner_service``) avoids a circular import between the two
dependency modules.
"""

from functools import lru_cache

from fastapi import Depends

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.agents.planner.parser.plan_parser import PlanParser
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.agents.planner.validation.plan_validator import PlannerPlanValidator
from backend.ai.prompts.manager import PromptManager
from backend.dependencies.adaptive import get_adaptive_planning_service
from backend.dependencies.ai import get_ai_service, get_prompt_manager
from backend.dependencies.memory import get_memory_service
from backend.memory.services.memory_service import MemoryService
from backend.services.ai_service import AIService
from backend.services.planner_service import PlannerService


@lru_cache
def get_plan_parser() -> PlanParser:
    """Return the process-wide PlanParser singleton (stateless, safe to share)."""
    return PlanParser()


@lru_cache
def get_planner_plan_validator() -> PlannerPlanValidator:
    """Return the process-wide PlannerPlanValidator singleton (stateless, safe to share)."""
    return PlannerPlanValidator()


def get_planner_service(
    ai_service: AIService = Depends(get_ai_service),
    prompt_manager: PromptManager = Depends(get_prompt_manager),
    parser: PlanParser = Depends(get_plan_parser),
    validator: PlannerPlanValidator = Depends(get_planner_plan_validator),
    memory_service: MemoryService = Depends(get_memory_service),
    adaptive_planning_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> PlannerService:
    """Provide the PlannerService — the only object that should be used to generate plans."""
    return PlannerService(ai_service, prompt_manager, parser, validator, memory_service, adaptive_planning_service)


@lru_cache
def get_planner_agent_result_store() -> PlannerAgentResultStore:
    """Return the process-wide PlannerAgentResultStore singleton.

    Cached for the same reason as ``get_report_agent_result_store``: a
    result produced by one request (or one graph run) must still be
    fetchable in a later one.
    """
    return PlannerAgentResultStore()
