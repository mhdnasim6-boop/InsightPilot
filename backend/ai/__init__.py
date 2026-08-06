"""Provider-agnostic AI infrastructure.

Nothing outside this package (and ``backend.services.ai_service``, which
wraps it) should import an LLM SDK directly. Every provider — the mock
today, OpenAI/Anthropic/Ollama/Gemini later — implements the same
``backend.ai.providers.base.AIProvider`` interface, so callers never see
a provider-specific request, response, or client object.
"""
