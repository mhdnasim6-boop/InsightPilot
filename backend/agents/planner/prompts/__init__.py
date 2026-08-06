"""Reusable planner prompt templates, registered into the shared ``PromptManager``.

No prompt is registered at import time — ``register_planner_prompts()``
must be called (once, idempotently) against a real ``PromptManager``
instance, exactly as ``backend.ai.prompts`` documents for business/agent
code.
"""
