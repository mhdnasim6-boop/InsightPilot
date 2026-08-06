"""Planning-layer exceptions.

All inherit from ``backend.core.exceptions.InsightPilotError``, so the
existing global exception handlers convert them into the unified API
response envelope with no planning-specific special-casing.
"""
