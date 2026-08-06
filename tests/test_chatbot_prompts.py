"""Tests for chat prompt templates: registration, rendering, and per-intent style."""

from datetime import UTC, datetime

from backend.ai.prompts.manager import PromptManager
from backend.chatbot.context.models import ChatMessage
from backend.chatbot.prompts.templates import (
    PROMPT_NAMES,
    prompt_name_for_intent,
    register_chat_prompts,
    render_conversation_history,
    style_instruction_for_intent,
    summarize_dataset,
    system_prompt_for_intent,
)
from backend.chatbot.retrieval.classifier import Intent
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType


def test_register_chat_prompts_registers_every_intent() -> None:
    manager = PromptManager()
    register_chat_prompts(manager)

    for intent in Intent:
        assert manager.is_registered(prompt_name_for_intent(intent))


def test_register_chat_prompts_is_idempotent() -> None:
    manager = PromptManager()
    register_chat_prompts(manager)
    register_chat_prompts(manager)  # must not raise

    assert len(manager.list_names()) == len(PROMPT_NAMES)


def test_prompt_name_for_intent_falls_back_to_general_for_unregistered_lookup() -> None:
    assert prompt_name_for_intent(Intent.GENERAL) == "chat.general"


def test_every_intent_has_a_distinct_style_instruction() -> None:
    instructions = {style_instruction_for_intent(intent) for intent in Intent}
    assert len(instructions) == len(list(Intent))


def test_rendered_prompt_contains_all_supplied_facts() -> None:
    manager = PromptManager()
    register_chat_prompts(manager)

    prompt = manager.get(
        prompt_name_for_intent(Intent.KPI),
        dataset_summary="sales.csv (100 rows, 3 columns)",
        facts="- Total Revenue: 1000",
        conversation_history="None yet - this is the first question.",
        question="What are the KPIs?",
    )

    assert "sales.csv (100 rows, 3 columns)" in prompt
    assert "- Total Revenue: 1000" in prompt
    assert "What are the KPIs?" in prompt
    # The grounding rule/system framing lives in the *system* prompt now, never
    # the user-visible one — see backend/chatbot/prompts/templates.py's own docstring.
    assert "never invent" not in prompt.lower()


def test_system_prompt_contains_the_grounding_rule_and_style_instruction() -> None:
    system_prompt = system_prompt_for_intent(Intent.KPI)

    assert "never invent" in system_prompt.lower()
    assert style_instruction_for_intent(Intent.KPI) in system_prompt


def test_every_intent_has_a_system_prompt() -> None:
    for intent in Intent:
        system_prompt = system_prompt_for_intent(intent)
        assert "InsightPilot" in system_prompt
        assert style_instruction_for_intent(intent) in system_prompt


def test_summarize_dataset_with_dataset() -> None:
    now = datetime.now(UTC)
    dataset = BusinessDataset(
        dataset_id="d1", dataset_name="sales.csv", source_type=SourceType.CSV, source_location="/tmp/sales.csv",
        row_count=100, column_count=3, created_at=now, loaded_at=now,
    )
    assert summarize_dataset(dataset) == "sales.csv (100 rows, 3 columns)"


def test_summarize_dataset_with_none() -> None:
    assert summarize_dataset(None) == "No dataset selected."


def test_render_conversation_history_empty() -> None:
    assert render_conversation_history([]) == "None yet - this is the first question."


def test_render_conversation_history_formats_roles() -> None:
    history = [
        ChatMessage(role="user", content="Hi", timestamp=datetime.now(UTC)),
        ChatMessage(role="assistant", content="Hello!", timestamp=datetime.now(UTC)),
    ]
    rendered = render_conversation_history(history)

    assert rendered == "User: Hi\nAssistant: Hello!"


def test_render_conversation_history_truncates_to_limit() -> None:
    history = [ChatMessage(role="user", content=f"message {i}", timestamp=datetime.now(UTC)) for i in range(10)]
    rendered = render_conversation_history(history, limit=3)

    assert "message 0" not in rendered
    assert "message 9" in rendered
    assert rendered.count("User:") == 3
