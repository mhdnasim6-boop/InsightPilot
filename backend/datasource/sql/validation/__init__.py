"""Connection config shape checks and validation results."""

from backend.datasource.sql.validation.checks import check_connection_config
from backend.datasource.sql.validation.result import ConnectionValidationResult

__all__ = ["ConnectionValidationResult", "check_connection_config"]
