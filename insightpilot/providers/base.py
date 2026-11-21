"""The vendor-agnostic AIProvider interface.

Agents never import Ollama or OpenAI classes. They receive an AIProvider and use
only the three operations below, so the model vendor can be swapped with one
configuration setting.

  chat()            plain text reply
  structured()      a validated Pydantic object (with one repair retry)
  get_chat_model()  a LangChain chat model, for tool loops and prebuilt agents
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderUnavailable(RuntimeError):
    """The model backend cannot be reached or is not configured (Ollama down, no API key...)."""


class StructuredOutputError(RuntimeError):
    """The model could not produce a valid object for the requested schema."""


_CONNECTION_ERROR_NAMES = (
    "ConnectError", "ConnectionError", "APIConnectionError", "AuthenticationError",
    "PermissionDeniedError", "ConnectTimeout", "ReadTimeout", "APITimeoutError",
)


def is_connection_error(exc: BaseException) -> bool:
    """True for errors meaning 'the backend is not reachable / not authorised'."""
    if isinstance(exc, ProviderUnavailable):
        return True
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if type(exc).__name__ in _CONNECTION_ERROR_NAMES or isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        # Ollama reports a missing model as ResponseError(404)
        if type(exc).__name__ == "ResponseError" and "not found" in str(exc).lower():
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def message_text(content: Any) -> str:
    """Normalise LangChain message content (str or list of blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


class AIProvider(ABC):
    name: str = "base"
    model_name: str = ""

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """Return a LangChain chat model (supports bind_tools for tool loops)."""

    # ---- shared behaviour -------------------------------------------------
    def chat(self, messages: Sequence[BaseMessage]) -> str:
        reply = self.get_chat_model().invoke(list(messages))
        return message_text(reply.content)

    def _invoke_structured(self, messages: list[BaseMessage], schema: type[BaseModel]) -> Any:
        """Provider-specific structured call. Subclasses override when a vendor needs a different method."""
        return self.get_chat_model().with_structured_output(schema).invoke(messages)

    def structured(self, messages: Sequence[BaseMessage], schema: type[T], max_retries: int = 1) -> T:
        """Return a validated `schema` object.

        If the model's output is missing or invalid, retry up to `max_retries` times with the
        validation error appended, so the model can correct itself. Connection problems are not
        retried; they raise ProviderUnavailable immediately.
        """
        base = list(messages)
        msgs = list(base)
        last_err: Exception | None = None
        for _ in range(max_retries + 1):
            try:
                raw = self._invoke_structured(msgs, schema)
                if raw is None:
                    raise ValueError("the model returned no structured output")
                return raw if isinstance(raw, schema) else schema.model_validate(raw)
            except Exception as exc:  # noqa: BLE001 - classified below
                if is_connection_error(exc):
                    raise ProviderUnavailable(f"{self.name}: {exc}") from exc
                last_err = exc
                short = str(exc).replace("\n", " ")[:300]
                msgs = base + [HumanMessage(
                    content=f"Your previous answer was not valid ({short}). "
                            f"Reply again with ONLY a valid object for the schema."
                )]
        raise StructuredOutputError(
            f"{self.name} could not produce a valid {schema.__name__}: {last_err}"
        ) from last_err

    def describe(self) -> str:
        return f"{self.name} ({self.model_name})"
