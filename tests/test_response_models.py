"""Tests for the unified API response envelope models."""

from backend.schemas.errors import ErrorDetail, ErrorResponse
from backend.schemas.health import HealthResponse
from backend.schemas.response import SuccessResponse


def test_success_response_shape() -> None:
    payload = HealthResponse(status="healthy", application="InsightPilot", version="0.1.0")
    response = SuccessResponse.ok(data=payload, message="ok")

    dumped = response.model_dump()
    assert dumped["success"] is True
    assert dumped["message"] == "ok"
    assert dumped["data"]["status"] == "healthy"


def test_error_response_shape() -> None:
    error = ErrorResponse(
        message="Not found.",
        errors=ErrorDetail(type="NotFoundError", status_code=404, path="/api/v1/x"),
    )

    dumped = error.model_dump()
    assert dumped["success"] is False
    assert dumped["message"] == "Not found."
    assert dumped["errors"]["type"] == "NotFoundError"
    assert dumped["errors"]["status_code"] == 404
