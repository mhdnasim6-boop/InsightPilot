"""Best-effort AI cost estimation: a small, clearly-labeled per-provider/
per-model $-per-1000-tokens lookup, not a billing-accurate ledger.

``mock``/``ollama`` always cost $0 (no network call, or a local model
with no per-token billing). The ``anthropic``/``openai`` model entries
beyond what's wired up today exist so a real provider dropped into the
same registry later gets a sane estimate for free — this table needs
updating only if pricing changes, never if a new agent/tool is added.
"""

from backend.ai.models.responses import TokenUsage

# USD per 1000 tokens, (prompt_rate, completion_rate). Unknown provider/model -> $0.
_RATES: dict[str, tuple[float, float]] = {
    "mock": (0.0, 0.0),
    "ollama": (0.0, 0.0),  # Runs on the user's own machine — no per-token cost.
    "openai:gpt-4o": (0.005, 0.015),
    "openai:gpt-4o-mini": (0.00015, 0.0006),
    "anthropic:claude-sonnet": (0.003, 0.015),
    "anthropic:claude-haiku": (0.0008, 0.004),
}


def estimate_cost(provider: str, model: str, usage: TokenUsage) -> float:
    """Estimate a call's cost in USD from its token usage. Returns 0.0 for unrecognized providers/models."""
    key = f"{provider.strip().lower()}:{model.strip().lower()}"
    prompt_rate, completion_rate = _RATES.get(key, _RATES.get(provider.strip().lower(), (0.0, 0.0)))
    return (usage.prompt_tokens / 1000) * prompt_rate + (usage.completion_tokens / 1000) * completion_rate
