"""Application-wide configuration, loaded from environment variables / .env.

This is the single source of truth for configuration values. No module in
``backend`` or ``frontend`` should read ``os.environ`` directly or hardcode
a value that belongs here — they should depend on :func:`get_settings`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings.

    Values are resolved from environment variables first, falling back to
    a local ``.env`` file, then to the defaults declared below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "InsightPilot"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    frontend_url: str = "http://localhost:8501"
    backend_url: str = "http://localhost:8000"

    log_level: str = "INFO"

    # AI configuration — provider-agnostic; consumed by backend.ai / backend.services.ai_service.
    # Values here are defaults only: nothing in the AI layer hardcodes a provider, model, or limit.
    # Default stays "mock" deliberately (not "auto") — the whole test suite depends on a
    # deterministic, network-free provider when nothing is explicitly configured; set
    # AI_DEFAULT_PROVIDER=auto (or "ollama"/"openai" directly) for a real deployment.
    ai_default_provider: str = "mock"
    ai_default_model: str = "mock-model"
    ai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ai_max_tokens: int = Field(default=1024, gt=0)
    ai_timeout_seconds: float = Field(default=30.0, gt=0.0)
    ai_streaming_enabled: bool = True
    ai_retry_count: int = Field(default=2, ge=0)

    # Ollama (local LLM server) — see backend.ai.providers.ollama.OllamaProvider.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"

    # OpenAI (or an OpenAI-compatible endpoint) — see backend.ai.providers.openai.OpenAIProvider.
    # No default api_key: its absence is exactly what tells provider auto-detection
    # (backend.ai.providers.detection.ProviderDetector) that OpenAI isn't configured.
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Plugin & Extension SDK — filesystem directory PluginLoader scans (immediate
    # subfolders only) for third-party plugins. Never read anywhere but
    # backend.dependencies.plugins.
    plugin_extensions_dir: str = "backend/extensions"

    # Operations layer (Phase 34) — a plain string here, not a
    # backend.operations.configuration.ConfigurationProfileName import, so
    # config/ never depends on backend/ (mirrors plugin_extensions_dir's
    # own precedent above). Validated against the closed enum of known
    # profile names by ConfigurationLoader, not here.
    active_profile: str = "development"

    # Feature flags (Phase 34) — runtime-readable only; see
    # backend.operations.feature_flags. Every flag defaults to the
    # always-on behavior every earlier phase already shipped, so setting
    # none of these changes anything: the flags are observable/reportable
    # infrastructure, not enforcement — no subsystem's own logic reads
    # these fields, to satisfy "do not modify Memory/Reflection/Adaptive
    # Planning/Collaboration/Plugin logic."
    memory_enabled: bool = True
    plugins_enabled: bool = True
    reflection_enabled: bool = True
    adaptive_planning_enabled: bool = True
    browser_agent_enabled: bool = True
    mcp_enabled: bool = True

    # Security (Phase 35) — JWT signing/expiry. jwt_secret_key's default is
    # intentionally recognizable ("insecure-dev-secret...") so
    # backend.security.authentication.jwt_service.JWTService can (and does)
    # log a loud warning if it's still in effect — never enforced/raised
    # here, since config/ has no opinion on what "production" means beyond
    # the existing environment field.
    jwt_secret_key: str = "insecure-dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, gt=0)
    jwt_refresh_token_expire_minutes: int = Field(default=60 * 24 * 7, gt=0)
    jwt_clock_skew_seconds: int = Field(default=30, ge=0)

    # First-run bootstrap admin account — see
    # backend.security.users.user_service.UserService.ensure_default_admin(),
    # called once by backend.dependencies.security.get_user_service(). Same
    # "recognizable insecure default" convention as jwt_secret_key above.
    security_admin_username: str = "admin"
    security_admin_password: str = "ChangeMe123!"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Cached with ``lru_cache`` so the environment/``.env`` is parsed once per
    process, while still being a normal callable that FastAPI can inject via
    ``Depends(get_settings)``.
    """
    return Settings()
