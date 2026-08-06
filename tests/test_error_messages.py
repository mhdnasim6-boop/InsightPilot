"""Tests for frontend.components.error_messages.describe_error: every caught
APIClientError must produce a friendly title/message/suggestion, never surfacing a
raw backend error_type/status code as the primary message.
"""

from frontend.api.exceptions import APIClientError, APIError, BackendUnavailableError
from frontend.components.error_messages import describe_error


def test_backend_unavailable_gets_a_friendly_connectivity_message() -> None:
    friendly = describe_error(BackendUnavailableError("Connection refused"))
    assert friendly.title == "Can't reach the backend"
    assert "Connection refused" in (friendly.technical_detail or "")
    assert "ConnectionError" not in friendly.message


def test_401_tells_the_user_to_log_in_again() -> None:
    friendly = describe_error(APIError("Not authenticated", 401, "AuthenticationError"))
    assert "signed out" in friendly.title.lower()
    assert "log in" in friendly.suggestion.lower()


def test_403_explains_missing_permission() -> None:
    friendly = describe_error(APIError("Forbidden", 403, "AuthorizationError"))
    assert "permission" in friendly.title.lower()


def test_404_humanizes_a_not_found_error_type_into_the_message() -> None:
    friendly = describe_error(APIError("No cluster", 404, "ClusterNotFoundError"))
    assert friendly.message == "Cluster not found."


def test_404_without_not_found_suffix_uses_the_generic_template() -> None:
    friendly = describe_error(APIError("Missing", 404, "SomeOtherError"))
    assert "doesn't exist" in friendly.message


def test_422_includes_the_raw_validation_detail_in_technical_detail_only() -> None:
    detail = [{"loc": ["body", "memory_type"], "msg": "Input should be 'fact'"}]
    friendly = describe_error(APIError("Request validation failed.", 422, "ValidationError", detail=detail))
    assert "ValidationError" not in friendly.message
    assert "422" not in friendly.message
    assert friendly.technical_detail is not None
    assert "ValidationError (422)" in friendly.technical_detail
    assert "memory_type" in friendly.technical_detail


def test_500_gets_a_generic_apologetic_message() -> None:
    friendly = describe_error(APIError("Internal error", 500, "AutonomousError"))
    assert "went wrong" in friendly.title.lower()


def test_unmapped_status_code_falls_back_to_the_default_template() -> None:
    friendly = describe_error(APIError("teapot", 418, "TeapotError"))
    assert friendly.title == "Something went wrong"


def test_plain_api_client_error_still_produces_a_friendly_fallback() -> None:
    friendly = describe_error(APIClientError("No active session and the backend is unreachable."))
    assert friendly.title == "Something went wrong"
    assert friendly.technical_detail == "No active session and the backend is unreachable."
