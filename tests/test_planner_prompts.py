"""Tests for planner prompt category selection and registration."""

import json

import pytest

from backend.agents.planner.examples.plan_examples import PLAN_EXAMPLES
from backend.agents.planner.prompts.templates import (
    DEFAULT_CATEGORY,
    PROMPT_NAMES,
    prompt_name_for_category,
    register_planner_prompts,
    select_category,
)
from backend.ai.prompts.manager import PromptManager


@pytest.mark.parametrize(
    ("user_request", "expected_category"),
    [
        ("Please clean this messy dataset", "data_cleaning_request"),
        ("Generate a report on quarterly sales", "report_generation"),
        ("Generate a report with recent market context", "report_with_market_context"),
        ("Compare Q1 vs Q2 sales", "comparison_request"),
        ("Analyze the customer table from SQL", "sql_analysis"),
        ("Analyze this uploaded CSV for trends", "csv_analysis"),
        ("Give me business recommendations from the executive summary", "executive_summary_only"),
        ("What was our best-selling product?", DEFAULT_CATEGORY),
    ],
)
def test_select_category_matches_expected_keywords(user_request: str, expected_category: str) -> None:
    assert select_category(user_request) == expected_category


def test_select_category_is_case_insensitive() -> None:
    assert select_category("PLEASE CLEAN THIS DATA") == "data_cleaning_request"


def test_prompt_name_for_category_known_and_unknown() -> None:
    assert prompt_name_for_category("report_generation") == "planner.report_generation"
    assert prompt_name_for_category("not-a-real-category") == PROMPT_NAMES[DEFAULT_CATEGORY]


def test_register_planner_prompts_registers_every_category() -> None:
    prompt_manager = PromptManager()
    register_planner_prompts(prompt_manager)
    for name in PROMPT_NAMES.values():
        assert prompt_manager.is_registered(name)


def test_register_planner_prompts_is_idempotent() -> None:
    prompt_manager = PromptManager()
    register_planner_prompts(prompt_manager)
    register_planner_prompts(prompt_manager)  # must not raise
    assert len(prompt_manager.list_names()) >= len(PROMPT_NAMES)


@pytest.mark.parametrize("category", list(PLAN_EXAMPLES))
def test_every_registered_prompt_renders_with_a_json_example_without_error(category: str) -> None:
    prompt_manager = PromptManager()
    register_planner_prompts(prompt_manager)
    name = prompt_name_for_category(category)
    example_json = json.dumps(PLAN_EXAMPLES[category], indent=2)

    rendered = prompt_manager.get(
        name,
        available_services="file_agent, sql_agent, browser_agent, report_agent, executive_summary_agent",
        datasets_summary="None uploaded.",
        conversation_summary="None.",
        sql_connections_summary="None declared.",
        browser_context_summary="None declared.",
        existing_reports_summary="None.",
        example_json=example_json,
        user_request="do something",
    )

    assert "do something" in rendered
    assert example_json in rendered
