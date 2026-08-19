"""Application entry point."""

import logging

import uvicorn
from fastapi import FastAPI

from redirector.config import Settings
from redirector.repository import SqliteRedirectRepository
from redirector.routes import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_application(settings: Settings | None = None) -> FastAPI:
    """Create and configure the application.

    Args:
        settings: Optional settings instance. Created from environment if None.

    Returns:
        A configured FastAPI application.
    """
    if settings is None:
        settings = Settings()
    repository = SqliteRedirectRepository(settings.sqlite_path)
    return create_app(repository)


def main() -> None:
    """Entry point for the redirector server."""
    settings = Settings()
    logger.info("Starting redirector on port %d", settings.port)
    logger.info("Database backend: %s", settings.db_backend)
    if settings.db_backend == "sqlite":
        logger.info("SQLite path: %s", settings.sqlite_path)

    uvicorn.run(
        "redirector.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )


# Module-level app for uvicorn direct usage (e.g., uvicorn redirector.main:app)
app = create_application()
