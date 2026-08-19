"""HTTP route handlers."""

import logging

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse

from redirector.repository import RedirectRepository

logger = logging.getLogger(__name__)


def create_app(repository: RedirectRepository) -> FastAPI:
    """Create the FastAPI application with routes.

    Args:
        repository: The redirect repository to use for lookups.

    Returns:
        A configured FastAPI application.
    """
    app = FastAPI(title="Redirector", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint."""
        return {"status": "ok"}

    @app.get("/favicon.ico", response_model=None)
    def favicon() -> Response:  # pyright: ignore[reportUnusedFunction]
        """Return empty response for favicon requests."""
        return Response(status_code=204)

    @app.get("/", response_model=None)
    def index() -> Response:  # pyright: ignore[reportUnusedFunction]
        """List all available redirects."""
        entries = repository.list_redirects()
        shortcuts = [
            {"short_code": e.short_code, "url": e.destination_url} for e in entries
        ]
        return JSONResponse(content={"redirects": shortcuts})

    @app.get("/{short_code:path}", response_model=None)
    def redirect(short_code: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Look up a short code and redirect to the destination URL."""
        normalized = short_code.lower()
        entry = repository.get_redirect(normalized)

        if entry is None or not entry.enabled:
            logger.info("Short code not found or disabled: %s", normalized)
            return JSONResponse(
                status_code=404,
                content={"error": "not found"},
            )

        logger.info(
            "Redirecting %s -> %s (%d)",
            normalized,
            entry.destination_url,
            entry.status_code,
        )
        return RedirectResponse(
            url=entry.destination_url,
            status_code=entry.status_code,
        )

    return app
