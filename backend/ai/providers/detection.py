"""ProviderDetector: resolves the "auto" provider choice to a concrete provider
name, once, cheaply, with a bounded timeout — never blocks the app for long and
never raises.

Deliberately synchronous (mirrors ``ProviderFactory.create()``'s own existing
signature) rather than async: making detection async would force
``ProviderFactory.create()`` to become async too, which cascades into
``ConfigurationValidator._check_ai_provider()`` (a synchronous startup
validator that already calls ``.create()`` directly) — a far bigger, riskier
change than this phase's own "refinement only" scope allows. A short
(~1.5s), synchronous, timeout-bounded HTTP probe at process startup (and
cached after that) is a well-established, acceptable tradeoff.

Priority, matching this phase's own spec exactly: Ollama reachable? -> use
it. Else an OpenAI API key configured? -> use that. Else -> Mock.
"""

import httpx

from config.settings import Settings

_DETECTION_TIMEOUT_SECONDS = 1.5


class ProviderDetector:
    """Resolves ``"auto"`` to a concrete provider name once per process, then caches it.

    An explicitly-configured (non-``"auto"``) ``ai_default_provider`` always
    passes through unchanged and is never cached — there's nothing to detect.
    """

    def __init__(self) -> None:
        self._cached_name: str | None = None

    def resolve(self, settings: Settings) -> str:
        """Return the effective provider name for ``settings``."""
        configured = settings.ai_default_provider.strip().lower()
        if configured != "auto":
            return configured
        if self._cached_name is None:
            self._cached_name = self._detect(settings)
        return self._cached_name

    def refresh(self, settings: Settings) -> str:
        """Force re-detection (used by the Settings page's own Test Connection flow
        and by tests) — ignored entirely when ``ai_default_provider`` isn't ``"auto"``."""
        self._cached_name = self._detect(settings)
        return self._cached_name

    def _detect(self, settings: Settings) -> str:
        if self._ollama_reachable(settings):
            return "ollama"
        if settings.openai_api_key:
            return "openai"
        return "mock"

    def _ollama_reachable(self, settings: Settings) -> bool:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
        try:
            response = httpx.get(url, timeout=_DETECTION_TIMEOUT_SECONDS)
        except httpx.HTTPError:
            return False
        return response.status_code == 200
