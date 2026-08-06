"""HTTP client for the InsightPilot backend API — the dashboard's only backend dependency."""

from frontend.api.client import APIClient
from frontend.api.exceptions import APIClientError, APIError, BackendUnavailableError

__all__ = ["APIClient", "APIClientError", "APIError", "BackendUnavailableError"]
