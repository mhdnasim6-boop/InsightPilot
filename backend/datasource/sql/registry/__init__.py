"""Database-type-keyed connector dispatch — no if/else chains."""

from backend.datasource.sql.registry.connector_registry import ConnectorRegistry

__all__ = ["ConnectorRegistry"]
