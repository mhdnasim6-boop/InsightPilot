"""Result of validating a connection — config shape and, if that passes, real connectivity."""

from pydantic import BaseModel, Field

from backend.datasource.sql.models.connection_config import DatabaseType
from backend.ingestion.validators.result import ValidationIssue


class ConnectionValidationResult(BaseModel):
    """The outcome of :meth:`SQLConnector.validate`."""

    is_valid: bool
    database_type: DatabaseType
    message: str
    issues: list[ValidationIssue] = Field(default_factory=list)
