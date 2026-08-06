"""Tests for AI-related configuration validation on Settings."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from config.settings import Settings


def test_ai_defaults_are_sane() -> None:
    settings = Settings()
    assert settings.ai_default_provider == "mock"
    assert settings.ai_streaming_enabled is True
    assert settings.ai_retry_count >= 0


def test_ai_temperature_out_of_range_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(ai_temperature=10.0)


def test_ai_max_tokens_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(ai_max_tokens=0)


def test_ai_timeout_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(ai_timeout_seconds=0)


def test_ai_retry_count_cannot_be_negative() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(ai_retry_count=-1)
