"""Scripted provider for automated tests (and nothing else).

It returns pre-written responses instead of calling a model, so graph behaviour
(routing, retries, approvals, memory) can be tested quickly, repeatably and for free.
It is deliberately NOT registered in the factory: the application never uses it.
"""
from __future__ import annotations

from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field

from .base import AIProvider


class ScriptedChatModel(BaseChatModel):
    """A chat model that returns queued AIMessages (including ones with tool_calls)."""

    responses: list = Field(default_factory=list)
    calls: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # the script already decides which tools are called
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        if not self.responses:
            raise RuntimeError("ScriptedChatModel: no scripted response left")
        item = self.responses.pop(0)
        msg = item(messages) if callable(item) else item
        if isinstance(msg, Exception):
            raise msg
        return ChatResult(generations=[ChatGeneration(message=msg)])


class MockProvider(AIProvider):
    name = "mock"
    model_name = "scripted"

    def __init__(self):
        self.structured_script: dict[str, list[Any]] = {}   # schema name -> queue
        self.chat_model = ScriptedChatModel()
        self.chat_script: list[str] = []
        self.log: list[tuple[str, str]] = []

    # -- scripting helpers --
    def script_structured(self, schema_name: str, *items: Any) -> "MockProvider":
        self.structured_script.setdefault(schema_name, []).extend(items)
        return self

    def script_model(self, *messages: Any) -> "MockProvider":
        self.chat_model.responses.extend(messages)
        return self

    def script_chat(self, *texts: str) -> "MockProvider":
        self.chat_script.extend(texts)
        return self

    # -- AIProvider API --
    def get_chat_model(self) -> BaseChatModel:
        return self.chat_model

    def chat(self, messages):
        self.log.append(("chat", ""))
        if self.chat_script:
            return self.chat_script.pop(0)
        return "ok"

    def _invoke_structured(self, messages, schema: type[BaseModel]) -> Any:
        self.log.append(("structured", schema.__name__))
        queue = self.structured_script.get(schema.__name__)
        if not queue:
            raise RuntimeError(f"MockProvider: no scripted response for {schema.__name__}")
        item = queue.pop(0)
        if callable(item) and not isinstance(item, BaseModel):
            item = item(messages)
        if isinstance(item, Exception):
            raise item
        return item
