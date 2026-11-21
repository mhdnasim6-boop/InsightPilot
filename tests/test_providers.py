import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from insightpilot.config import Settings
from insightpilot.providers.base import AIProvider, ProviderUnavailable, StructuredOutputError, is_connection_error
from insightpilot.providers.factory import PROVIDER_NAMES, get_provider
from insightpilot.providers.mock_provider import MockProvider
from insightpilot.providers.ollama_provider import OllamaProvider
from insightpilot.providers.openai_provider import OpenAIProvider


class Thing(BaseModel):
    n: int


def test_factory_switches_on_name(settings):
    assert isinstance(get_provider("ollama", settings), OllamaProvider)
    s = settings.with_overrides(openai_api_key="sk-test")
    assert isinstance(get_provider("openai", s), OpenAIProvider)
    assert all(isinstance(get_provider(n, s), AIProvider) for n in PROVIDER_NAMES)


def test_factory_reads_env_switch(monkeypatch, tmp_path):
    monkeypatch.setenv("INSIGHTPILOT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert get_provider(settings=Settings.from_env()).name == "openai"
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert get_provider(settings=Settings.from_env()).name == "ollama"


def test_unknown_provider_is_a_clear_error(settings):
    with pytest.raises(ValueError, match="Unknown"):
        get_provider("gemini", settings)


def test_openai_without_key_is_unavailable(settings):
    with pytest.raises(ProviderUnavailable):
        get_provider("openai", settings.with_overrides(openai_api_key="")).get_chat_model()


def test_ollama_defaults_to_qwen(settings):
    assert get_provider("ollama", settings).model_name == "qwen2.5:3b"


def test_structured_retries_once_then_succeeds():
    p = MockProvider().script_structured("Thing", ValueError("bad json"), Thing(n=3))
    assert p.structured([HumanMessage(content="x")], Thing).n == 3


def test_structured_gives_up_with_clear_error():
    p = MockProvider().script_structured("Thing", ValueError("bad"), ValueError("worse"))
    with pytest.raises(StructuredOutputError):
        p.structured([HumanMessage(content="x")], Thing)


def test_connection_errors_are_not_retried():
    p = MockProvider().script_structured("Thing", ConnectionError("refused"), Thing(n=1))
    with pytest.raises(ProviderUnavailable):
        p.structured([HumanMessage(content="x")], Thing)
    assert is_connection_error(ConnectionError("x"))
