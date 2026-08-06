"""AI-infrastructure exceptions.

All inherit from ``backend.core.exceptions.InsightPilotError``, so the
project's existing global exception handlers convert them into the
unified API response envelope with no AI-specific special-casing.
"""
