"""Tests for ChatContext/ChatMessage — construction and JSON round-tripping."""

from datetime import UTC, datetime

from backend.chatbot.context.models import ChatContext, ChatMessage


def test_chat_context_defaults() -> None:
    context = ChatContext(session_id="s1")

    assert context.selected_dataset is None
    assert context.cleaning_outcome is None
    assert context.analysis_result is None
    assert context.visualization_result is None
    assert context.execution_plan is None
    assert context.conversation_history == []
    assert context.user_preferences == {}
    assert context.metadata == {}


def test_chat_message_round_trips_through_json() -> None:
    message = ChatMessage(role="user", content="What are the KPIs?", timestamp=datetime.now(UTC))

    restored = ChatMessage.model_validate_json(message.model_dump_json())

    assert restored == message


def test_chat_context_holds_conversation_history_in_order() -> None:
    history = [
        ChatMessage(role="user", content="Hi", timestamp=datetime.now(UTC)),
        ChatMessage(role="assistant", content="Hello! How can I help?", timestamp=datetime.now(UTC)),
    ]
    context = ChatContext(session_id="s1", conversation_history=history)

    assert [message.role for message in context.conversation_history] == ["user", "assistant"]


def test_chat_context_round_trips_through_json() -> None:
    context = ChatContext(session_id="s1", user_preferences={"tone": "concise"}, metadata={"source": "dashboard"})

    restored = ChatContext.model_validate_json(context.model_dump_json())

    assert restored == context
