"""InsightPilot FastAPI application factory.

Run with: ``uv run uvicorn backend.main:app --reload``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.ai.providers.detection import ProviderDetector
from backend.api.v1.router import router as v1_router
from backend.core.exceptions import ConfigurationError
from backend.dependencies.operations import (
    resolve_shutdown_manager,
    resolve_startup_manager,
)
from backend.dependencies.plugins import get_plugin_registry
from backend.dependencies.realtime import resolve_realtime_service
from backend.dependencies.security import (
    resolve_audit_service,
    resolve_authentication_service,
)
from backend.dependencies.tools import get_tool_registry
from backend.middleware.exception_handlers import register_exception_handlers
from backend.middleware.request_logging import RequestLoggingMiddleware
from backend.operations.configuration.configuration_loader import ConfigurationLoader
from backend.operations.startup.startup_manager import StageStatus
from backend.realtime.websocket.websocket_router import (
    router as realtime_websocket_router,
)
from backend.security.middleware.authentication import AuthenticationMiddleware
from backend.security.middleware.request_context import RequestContextMiddleware
from config.settings import Settings, get_settings
from shared.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run every startup stage once (Phase 34's own StartupManager), then run every
    shutdown stage once, in reverse, on the way out.

    Delegates the actual "Configuration -> Plugin loading -> Registries ->
    Memory -> Observability -> Execution -> API ready" sequence to
    ``StartupManager`` (``backend.dependencies.operations.resolve_startup_manager``)
    rather than inlining it here — this function's only remaining job is
    to run it once and log the outcome. A failed stage never raises past
    ``StartupManager.run()`` (see its own docstring): the app still comes
    up, but ``GET /api/v1/operations/readiness`` will honestly report
    ``ready: false`` until whatever failed is fixed and the process is
    restarted — the standard "liveness stays up, readiness reflects
    reality" split, not a crash.

    ``resolve_startup_manager()``/``resolve_shutdown_manager()`` call
    their underlying ``@lru_cache``'d DI providers manually (not via
    ``Depends()``, which only resolves inside a request) using the exact
    keyword-argument convention FastAPI's own dependency resolution uses
    internally — the same pattern this function used for
    ``get_plugin_registry`` alone in Phase 33; see that module's own
    docstring for why a positional call there would silently produce a
    second, divergent singleton.
    """
    settings = get_settings()
    logger.info(
        "Starting {} v{} [{}] (profile: {})",
        settings.app_name, settings.app_version, settings.environment, settings.active_profile,
    )

    startup_manager = resolve_startup_manager()
    report = startup_manager.run(profile=settings.active_profile)
    plugin_count = len(
        get_plugin_registry(tool_registry=get_tool_registry(), realtime_service=resolve_realtime_service()).list()
    )
    if report.completed:
        logger.info("Startup complete — {} stage(s), {} plugin(s) loaded.", len(report.stages), plugin_count)
    else:
        failed_stages = [stage.name for stage in report.stages if stage.status == StageStatus.FAILED]
        logger.warning(
            "Startup completed with failures in stage(s) {} — readiness will report not-ready.", failed_stages
        )

    _log_ai_provider(settings)

    yield

    resolve_shutdown_manager().run()
    logger.info("Shutting down {}", settings.app_name)


def _log_ai_provider(settings: Settings) -> None:
    """Log which AI provider will actually answer requests — one line, at startup,
    so "why does Chat sound like a mock" never requires digging through config.

    Additive, not part of ``StartupManager``'s own fixed stage sequence (Phase 34):
    resolving "auto" does real I/O (a short-timeout Ollama probe via
    ``ProviderDetector``), but it's read-only and never raises, so it doesn't need
    the stage machinery's status/rollback semantics — a failure here just means
    "couldn't tell", never "app is unhealthy".
    """
    resolved = ProviderDetector().resolve(settings)
    if resolved == "ollama":
        logger.info("AI Provider: Ollama ({})", settings.ollama_model)
    elif resolved == "openai":
        logger.info("AI Provider: OpenAI")
    else:
        logger.warning("AI Provider: Mock (development mode)")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Centralizing app construction here (rather than configuring a
    module-level ``app`` inline) keeps middleware/router/exception-handler
    wiring in one place and makes the app easy to re-instantiate in tests
    with different settings if needed.
    """
    settings = settings or get_settings()

    if settings.environment == "production" and settings.debug:
        raise ConfigurationError("DEBUG must not be enabled when ENVIRONMENT=production.")

    setup_logging(log_level=settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="InsightPilot API — Agentic AI-powered Business Intelligence Assistant.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    # Security (Phase 35). Added after CORS/RequestLogging, so — since Starlette runs
    # the *last*-added middleware *first* (confirmed empirically, not assumed) —
    # AuthenticationMiddleware sees every request before RequestLoggingMiddleware/CORS
    # do, and RequestContextMiddleware (added last of all) is outermost of every
    # middleware here, so request.state.request_id already exists by the time
    # AuthenticationMiddleware's own audit-logging call reads it.
    app.add_middleware(
        AuthenticationMiddleware,
        authentication_service=resolve_authentication_service(),
        audit_service=resolve_audit_service(),
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(v1_router)
    # Outside the /api/v1 prefix — this is a WebSocket route, not a versioned REST
    # resource, mirroring how /docs/redoc sit outside it too.
    app.include_router(realtime_websocket_router)

    return app


# Resolved through ConfigurationLoader (Phase 34), not get_settings() directly: the
# active profile's overrides (if any) are applied on top of the environment-resolved
# Settings before the app is built. With the default "development" profile — whose
# own overrides dict is empty by design — this is byte-for-byte identical to calling
# create_app() with no argument at all, so every existing caller (including every
# test that does ``from backend.main import app``) is completely unaffected unless
# ACTIVE_PROFILE is actually set to something else in the environment.
app = create_app(settings=ConfigurationLoader().load())
