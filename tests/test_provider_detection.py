"""Tests for ProviderDetector: resolving "auto" to a concrete provider name."""

import httpx
import pytest

from backend.ai.providers.detection import ProviderDetector
from config.settings import Settings


def _settings(**overrides: object) -> Settings:
    return Settings.model_validate(overrides)


def test_resolve_passes_through_an_explicit_non_auto_value() -> None:
    detector = ProviderDetector()
    assert detector.resolve(_settings(ai_default_provider="mock")) == "mock"


def test_resolve_is_case_and_whitespace_insensitive_for_explicit_values() -> None:
    detector = ProviderDetector()
    assert detector.resolve(_settings(ai_default_provider="  Mock  ")) == "mock"


def test_auto_resolves_to_ollama_when_ollama_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = ProviderDetector()
    monkeypatch.setattr(detector, "_ollama_reachable", lambda settings: True)

    resolved = detector.resolve(_settings(ai_default_provider="auto"))

    assert resolved == "ollama"


def test_auto_resolves_to_openai_when_ollama_is_unreachable_but_a_key_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = ProviderDetector()
    monkeypatch.setattr(detector, "_ollama_reachable", lambda settings: False)

    resolved = detector.resolve(_settings(ai_default_provider="auto", openai_api_key="sk-test"))

    assert resolved == "openai"


def test_auto_resolves_to_mock_when_nothing_else_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = ProviderDetector()
    monkeypatch.setattr(detector, "_ollama_reachable", lambda settings: False)

    resolved = detector.resolve(_settings(ai_default_provider="auto", openai_api_key=None))

    assert resolved == "mock"


def test_resolve_caches_the_detected_name_after_the_first_call(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = ProviderDetector()
    call_count = 0

    def _fake_reachable(settings: Settings) -> bool:
        nonlocal call_count
        call_count += 1
        return True

    monkeypatch.setattr(detector, "_ollama_reachable", _fake_reachable)
    settings = _settings(ai_default_provider="auto")

    detector.resolve(settings)
    detector.resolve(settings)

    assert call_count == 1


def test_refresh_re_detects_even_when_already_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    detector = ProviderDetector()
    reachable = True
    monkeypatch.setattr(detector, "_ollama_reachable", lambda settings: reachable)
    settings = _settings(ai_default_provider="auto")
    assert detector.resolve(settings) == "ollama"

    reachable = False
    assert detector.refresh(settings) == "mock"
    assert detector.resolve(settings) == "mock"  # the cache itself was updated, not just this call's return value


def test_ollama_reachable_returns_false_on_a_non_200_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    def fake_get(url: str, timeout: float) -> httpx.Response:
        return httpx.Client(transport=httpx.MockTransport(handle)).get(url)

    monkeypatch.setattr(httpx, "get", fake_get)
    detector = ProviderDetector()
    settings = _settings(ollama_base_url="http://127.0.0.1:11434")

    assert detector._ollama_reachable(settings) is False


def test_ollama_reachable_returns_true_on_a_200_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    def fake_get(url: str, timeout: float) -> httpx.Response:
        return httpx.Client(transport=httpx.MockTransport(handle)).get(url)

    monkeypatch.setattr(httpx, "get", fake_get)
    detector = ProviderDetector()
    settings = _settings(ollama_base_url="http://127.0.0.1:11434")

    assert detector._ollama_reachable(settings) is True


def test_ollama_reachable_returns_false_when_the_request_raises() -> None:
    detector = ProviderDetector()
    settings = _settings(ollama_base_url="http://127.0.0.1:1")  # nothing listens here
    assert detector._ollama_reachable(settings) is False
