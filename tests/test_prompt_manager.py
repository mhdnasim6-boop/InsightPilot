"""Tests for PromptManager."""

import pytest

from backend.ai.exceptions.errors import InvalidPromptError
from backend.ai.prompts.manager import PromptManager


def test_register_and_get() -> None:
    manager = PromptManager()
    manager.register("greeting", "Hello, {name}!")
    assert manager.get("greeting", name="Ada") == "Hello, Ada!"


def test_get_unregistered_prompt_raises() -> None:
    manager = PromptManager()
    with pytest.raises(InvalidPromptError):
        manager.get("missing")


def test_get_missing_variable_raises() -> None:
    manager = PromptManager()
    manager.register("greeting", "Hello, {name}!")
    with pytest.raises(InvalidPromptError):
        manager.get("greeting")


def test_register_empty_name_raises() -> None:
    manager = PromptManager()
    with pytest.raises(InvalidPromptError):
        manager.register("   ", "template")


def test_is_registered_and_list_names() -> None:
    manager = PromptManager()
    manager.register("a", "A")
    manager.register("b", "B")
    assert manager.is_registered("a") is True
    assert manager.is_registered("missing") is False
    assert manager.list_names() == ["a", "b"]
