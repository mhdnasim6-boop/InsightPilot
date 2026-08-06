"""Deterministic, network-free provider for tests and local development.

``_render()`` never echoes free-form prompt text back — doing so used to leak
this codebase's own internal chat prompt template (dataset context, retrieved
facts, conversation history, instructions) straight into what looked like an
AI answer to a human user. Instead, for a natural-language request, it picks
one of a small set of realistic, Markdown-formatted, business-analyst-style
canned responses by sniffing a couple of keywords in the prompt.

One narrow, deliberate exception: several agents (the Planner Agent chief
among them — see ``backend.agents.planner.prompts.templates``) embed a
worked JSON example directly in their own prompt template for few-shot
guidance, and their mock-mode tests have always relied on getting that same
JSON back as a valid, schema-passing "generated" plan — never on inventing a
fake one here, which would require duplicating real parsing/validation logic
this module has no business owning. A human chat user's prompt never
contains embedded JSON (the chat template is plain prose), so this exception
never affects the actual bug this phase exists to fix — it only preserves an
existing, unrelated testing mechanism for structured-output agents.
"""

import asyncio
from collections.abc import AsyncIterator

from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse, StreamingChunk, TokenUsage
from backend.ai.providers.base import AIProvider
from backend.ai.streaming.stream import AIStream
from backend.utils.time import utc_now

_DISCLAIMER = "\n\n*(Mock response — no real AI model is configured.)*"

_ANOMALY_RESPONSE = (
    "## Anomaly Analysis\n\n"
    "No significant anomalies were detected.\n\n"
    "Neither the Z-score nor the IQR method identified outliers in the numeric columns. "
    "The dataset appears internally consistent."
)
_TREND_RESPONSE = (
    "## Trend Analysis\n\n"
    "### Key Findings\n\n"
    "- The metric shows a steady trend across the observed period.\n"
    "- No sudden spikes or drops stand out from the surrounding values.\n\n"
    "### Observations\n\n"
    "- The overall direction is consistent with typical seasonal variation."
)
_CORRELATION_RESPONSE = (
    "## Correlation Analysis\n\n"
    "A notable relationship exists between the columns you asked about.\n\n"
    "- The relationship is consistent across the dataset.\n"
    "- Consider this a starting point for deeper analysis, not a causal claim."
)
_KPI_RESPONSE = (
    "## Key Performance Indicators\n\n"
    "### Summary\n\n"
    "- The core metrics for this dataset are within a typical range.\n"
    "- No individual KPI stands out as unusually high or low."
)
_SUMMARY_RESPONSE = (
    "## Dataset Summary\n\n"
    "This dataset appears clean and ready for exploratory analysis.\n\n"
    "### Key Findings\n\n"
    "- No missing values or duplicate rows were detected.\n"
    "- The numeric columns fall within a typical, consistent range.\n\n"
    "### Recommendations\n\n"
    "- Proceed to KPI or trend analysis for a deeper view."
)
_GENERAL_RESPONSE = (
    "## Response\n\n"
    "Here's a concise, business-oriented answer based on what's currently available.\n\n"
    "- The relevant facts have been reviewed.\n"
    "- No further action is required unless you'd like to explore a specific area further."
)

_KEYWORD_RESPONSES: tuple[tuple[str, str], ...] = (
    ("anomal", _ANOMALY_RESPONSE),
    ("outlier", _ANOMALY_RESPONSE),
    ("trend", _TREND_RESPONSE),
    ("correlat", _CORRELATION_RESPONSE),
    ("kpi", _KPI_RESPONSE),
    ("metric", _KPI_RESPONSE),
    ("summary", _SUMMARY_RESPONSE),
    ("summarize", _SUMMARY_RESPONSE),
    ("overview", _SUMMARY_RESPONSE),
)


class MockProvider(AIProvider):
    """Synthesizes a realistic, Markdown-formatted response — no network calls, never
    an echo of the prompt.

    Used as the default provider in tests and local development, and as
    the reference implementation any real provider must also satisfy.
    """

    provider_name = "mock"

    def __init__(self, default_model: str = "mock-model") -> None:
        self._default_model = default_model

    async def generate(self, request: AIRequest) -> AIResponse:
        """Return a deterministic, realistic-looking response derived from the prompt's
        own topic — never the prompt's own text."""
        model = request.model or self._default_model
        content = self._render(request)
        prompt_tokens = len(request.prompt.split())
        completion_tokens = len(content.split())
        return AIResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            finish_reason="stop",
        )

    def stream(self, request: AIRequest) -> AIStream:
        """Simulate streaming by yielding the deterministic response word by word."""
        return AIStream(self._generate_chunks(request))

    async def health_check(self) -> ProviderHealth:
        """Always healthy — there's no external dependency to fail."""
        return ProviderHealth(
            provider=self.provider_name,
            healthy=True,
            message="Mock provider has no external dependency and is always healthy.",
            checked_at=utc_now(),
        )

    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        """Describe the (mock) model with static, well-formed limits."""
        return ModelInfo(
            name=model or self._default_model,
            provider=self.provider_name,
            max_input_tokens=8192,
            max_output_tokens=2048,
            supports_streaming=True,
        )

    def _render(self, request: AIRequest) -> str:
        embedded_json = self._extract_embedded_json(request.prompt)
        if embedded_json is not None:
            return embedded_json

        haystack = request.prompt.lower()
        for keyword, response in _KEYWORD_RESPONSES:
            if keyword in haystack:
                return response + _DISCLAIMER
        return _GENERAL_RESPONSE + _DISCLAIMER

    def _extract_embedded_json(self, text: str) -> str | None:
        """Return the first balanced ``{...}`` substring in ``text``, or ``None``.

        Deliberately duplicated (not imported) from
        ``backend.agents.planner.parser.json_extractor.extract_json_object`` —
        ``backend.ai`` is foundational infrastructure every agent depends on;
        depending back on ``backend.agents`` would invert that layering for
        the sake of ~20 lines of dependency-free string scanning.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    async def _generate_chunks(self, request: AIRequest) -> AsyncIterator[StreamingChunk]:
        words = self._render(request).split(" ")
        last_index = len(words) - 1
        for index, word in enumerate(words):
            await asyncio.sleep(0)  # yield control, matching a real async stream
            is_final = index == last_index
            yield StreamingChunk(
                delta=word if index == 0 else f" {word}",
                index=index,
                is_final=is_final,
                finish_reason="stop" if is_final else None,
            )
