"""Centralized Loguru configuration shared by the backend and frontend.

Both applications call :func:`setup_logging` once at startup so console and
file logging behave identically regardless of which process is running.
"""

import sys

from loguru import logger

from shared.paths import PROJECT_ROOT

LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "insightpilot.log"

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"

_configured = False


def setup_logging(log_level: str = "INFO") -> None:
    """Configure Loguru sinks for console and rotating file output.

    Idempotent: Streamlit reruns the whole script on every user interaction,
    so this guards against re-registering sinks (and duplicate log lines)
    on every rerun.
    """
    global _configured
    if _configured:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level=log_level.upper(), colorize=True, format=_CONSOLE_FORMAT)
    logger.add(
        LOG_FILE,
        level=log_level.upper(),
        format=_FILE_FORMAT,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
    )

    _configured = True
    logger.debug("Logging configured (level={})", log_level.upper())
