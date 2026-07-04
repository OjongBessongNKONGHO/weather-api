import logging
import sys
from app.config import settings


def configure_logging() -> None:
    """
    Configures structured logging for the entire application.

    Called once at startup in main.py lifespan — every module that uses
    logging.getLogger(__name__) automatically inherits this configuration.

    Log level is controlled by the APP_ENV environment variable:
    - development: DEBUG — verbose output for local development
    - production:  INFO  — operational events only, no debug noise

    Format includes timestamp, level, module name and message so every
    log line is self-contained and machine-parseable. In production,
    logs are typically shipped to CloudWatch, Datadog or a log aggregator
    where the structured format enables filtering and alerting.

    Why not basicConfig() everywhere?
    Calling basicConfig() in multiple modules causes duplicate handlers
    and inconsistent formatting. Configuring once at startup from a
    dedicated module is the production pattern.
    """
    log_level = logging.DEBUG if settings.app_env == "development" else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    # Suppress noisy third-party loggers in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured — level=%s env=%s",
        logging.getLevelName(log_level),
        settings.app_env,
    )
