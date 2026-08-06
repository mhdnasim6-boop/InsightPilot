"""Tests for provider-independent AI request/response models."""

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse, StreamingChunk, TokenUsage
from backend.utils.time import utc_now


def test_ai_request_defaults() -> None:
    request = AIRequest(prompt="hello")
    assert request.model is None
    assert request.stream is False
    assert request.metadata == {}


def test_ai_request_temperature_out_of_range_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        AIRequest(prompt="hello", temperature=5.0)


def test_ai_request_max_tokens_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        AIRequest(prompt="hello", max_tokens=0)


def test_ai_response_and_usage() -> None:
    usage = TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8)
    response = AIResponse(content="hi", model="mock-model", provider="mock", usage=usage)
    assert response.usage.total_tokens == 8


def test_streaming_chunk_shape() -> None:
    chunk = StreamingChunk(delta="hi", index=0, is_final=True, finish_reason="stop")
    assert chunk.is_final is True


def test_model_info_defaults() -> None:
    info = ModelInfo(name="mock-model", provider="mock")
    assert info.supports_streaming is False


def test_provider_health() -> None:
    health = ProviderHealth(provider="mock", healthy=True, checked_at=utc_now())
    assert health.healthy is True
    assert isinstance(health.checked_at, datetime)
