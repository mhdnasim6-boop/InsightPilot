"""Unique identifier generation."""

import uuid


def generate_id() -> str:
    """Generate a unique, URL-safe identifier (a UUID4 hex string)."""
    return uuid.uuid4().hex
