"""HTTP route handlers."""

import logging
import re
from importlib.metadata import version as pkg_version

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, field_validator

from redirector.auth import User
from redirector.repository import RedirectRepository
from redirector.suggestions import find_suggestions

logger = logging.getLogger(__name__)

APP_VERSION = pkg_version("redirector")

RESERVED_PATHS = {"health", "favicon.ico"}
SHORT_CODE_PATTERN = re.compile(r"^[a-z0-9_-]+$")
MAX_SHORT_CODE_LENGTH = 128


class CreateRedirectRequest(BaseModel):
    """Request body for creating a redirect."""

    short_code: str
    url: str
    group: str
    status_code: int = 302
    public: bool = False

    @field_validator("short_code")
    @classmethod
    def validate_short_code(cls, v: str) -> str:
        """Validate the short code format."""
        v = v.lower()
        if not v or len(v) > MAX_SHORT_CODE_LENGTH:
            msg = f"Short code must be between 1 and {MAX_SHORT_CODE_LENGTH} characters"
            raise ValueError(msg)
        if not SHORT_CODE_PATTERN.match(v):
            msg = "Only lowercase alphanumeric, hyphens, and underscores allowed"
            raise ValueError(msg)
        if v in RESERVED_PATHS:
            msg = f"'{v}' is a reserved path"
            raise ValueError(msg)
        return v


class PatchRedirectRequest(BaseModel):
    """Request body for updating a redirect."""

    enabled: bool


class RedirectResponseModel(BaseModel):
    """Response body for a redirect entry."""

    short_code: str
    url: str
    status_code: int
    owner_group: str | None
    public: bool
    enabled: bool


def create_app(
    repository: RedirectRepository,
    user_override: User | None = None,
    suggestion_threshold: float = 0.6,
    max_suggestions: int = 5,
) -> FastAPI:
    """Create the FastAPI application with routes.

    Args:
        repository: The redirect repository to use for lookups.
        user_override: If set, bypass auth and use this user.
            Used for testing. Pass None to require real auth.
        suggestion_threshold: Minimum similarity for suggestions.
        max_suggestions: Maximum number of suggestions to show.

    Returns:
        A configured FastAPI application.
    """
    app = FastAPI(
        title="Redirector",
        version="0.1.0",
        description=(
            "A minimal URL redirection service with group-based multi-tenancy."
        ),
    )

    def get_current_user(
        authorization: str | None = Header(default=None),
    ) -> User | None:
        """Extract user from auth header or return override."""
        if user_override is not None:
            return user_override
        # In production, this would validate the JWT token.
        # For now, return None (unauthenticated) if no override.
        return None

    def require_user(
        user: User | None = Depends(get_current_user),
    ) -> User:
        """Require an authenticated user or raise 401."""
        if user is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Authentication required")
        return user

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint."""
        return {"status": "ok", "version": APP_VERSION}

    @app.get("/favicon.ico", response_model=None)
    def favicon() -> Response:  # pyright: ignore[reportUnusedFunction]
        """Return empty response for favicon requests."""
        return Response(status_code=204)

    @app.get("/", response_model=None)
    def index(request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        """List all public redirects."""
        entries = repository.list_public()
        shortcuts = [
            {"short_code": e.short_code, "url": e.destination_url} for e in entries
        ]

        if _wants_json(request):
            return JSONResponse(content={"redirects": shortcuts})

        return HTMLResponse(content=_render_index_html(shortcuts))

    # --- Authenticated API endpoints ---

    @app.get("/api/redirects", response_model=None)
    def api_list_redirects(  # pyright: ignore[reportUnusedFunction]
        user: User = Depends(require_user),
    ) -> Response:
        """List redirects visible to the authenticated user."""
        entries = repository.list_by_groups(user.groups)
        redirects = [
            RedirectResponseModel(
                short_code=e.short_code,
                url=e.destination_url,
                status_code=e.status_code,
                owner_group=e.owner_group,
                public=e.public,
                enabled=e.enabled,
            ).model_dump()
            for e in entries
        ]
        return JSONResponse(content={"redirects": redirects})

    @app.post("/api/redirects", response_model=None, status_code=201)
    def api_create_redirect(  # pyright: ignore[reportUnusedFunction]
        body: CreateRedirectRequest,
        user: User = Depends(require_user),
    ) -> Response:
        """Create a new redirect entry."""
        # Check user belongs to the target group (or is admin)
        if not user.is_admin and body.group not in user.groups:
            return JSONResponse(
                status_code=403,
                content={"error": "Not a member of the target group"},
            )

        # Check for duplicates
        existing = repository.get_redirect(body.short_code)
        if existing is not None:
            return JSONResponse(
                status_code=409,
                content={"error": f"Short code '{body.short_code}' already exists"},
            )

        entry = repository.add_redirect(
            short_code=body.short_code,
            destination_url=body.url,
            status_code=body.status_code,
            owner_group=body.group,
            public=body.public,
        )
        return JSONResponse(
            status_code=201,
            content=RedirectResponseModel(
                short_code=entry.short_code,
                url=entry.destination_url,
                status_code=entry.status_code,
                owner_group=entry.owner_group,
                public=entry.public,
                enabled=entry.enabled,
            ).model_dump(),
        )

    @app.delete("/api/redirects/{short_code}", response_model=None)
    def api_delete_redirect(  # pyright: ignore[reportUnusedFunction]
        short_code: str,
        user: User = Depends(require_user),
    ) -> Response:
        """Delete a redirect entry."""
        entry = repository.get_redirect(short_code)
        if entry is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not found"},
            )

        # Check ownership
        if (
            not user.is_admin
            and entry.owner_group is not None
            and entry.owner_group not in user.groups
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Not authorized to manage this entry"},
            )

        repository.delete_redirect(short_code)
        return Response(status_code=204)

    @app.patch("/api/redirects/{short_code}", response_model=None)
    def api_patch_redirect(  # pyright: ignore[reportUnusedFunction]
        short_code: str,
        body: PatchRedirectRequest,
        user: User = Depends(require_user),
    ) -> Response:
        """Enable or disable a redirect entry."""
        entry = repository.get_redirect(short_code)
        if entry is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not found"},
            )

        # Check ownership
        if (
            not user.is_admin
            and entry.owner_group is not None
            and entry.owner_group not in user.groups
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Not authorized to manage this entry"},
            )

        repository.set_enabled(short_code, enabled=body.enabled)
        updated = repository.get_redirect(short_code)
        assert updated is not None
        return JSONResponse(
            content=RedirectResponseModel(
                short_code=updated.short_code,
                url=updated.destination_url,
                status_code=updated.status_code,
                owner_group=updated.owner_group,
                public=updated.public,
                enabled=updated.enabled,
            ).model_dump(),
        )

    @app.get("/{short_code:path}", response_model=None)
    def redirect(short_code: str, request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Look up a short code and redirect to the destination URL."""
        normalized = short_code.lower()
        entry = repository.get_redirect(normalized)

        if entry is None or not entry.enabled:
            logger.info("Short code not found or disabled: %s", normalized)
            return _not_found_response(
                normalized,
                request,
                repository,
                suggestion_threshold,
                max_suggestions,
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


def _wants_json(request: Request) -> bool:
    """Check if the client prefers JSON over HTML.

    Args:
        request: The incoming HTTP request.

    Returns:
        True if the client explicitly requests application/json.
    """
    accept = request.headers.get("accept", "")
    return "application/json" in accept


def _not_found_response(
    short_code: str,
    request: Request,
    repository: RedirectRepository,
    threshold: float,
    max_results: int,
) -> Response:
    """Build a 404 response with suggestions.

    Args:
        short_code: The short code that was not found.
        request: The incoming HTTP request (for content negotiation).
        repository: Repository to get public entries for suggestions.
        threshold: Minimum similarity for fuzzy matches.
        max_results: Maximum number of suggestions.

    Returns:
        JSON or HTML 404 response with suggestions.
    """
    public_entries = repository.list_public()
    candidates = [e.short_code for e in public_entries]
    suggestions = find_suggestions(
        short_code, candidates, threshold=threshold, max_results=max_results
    )

    if _wants_json(request):
        return JSONResponse(
            status_code=404,
            content={"error": "not found", "suggestions": suggestions},
        )

    return HTMLResponse(
        status_code=404,
        content=_render_404_html(short_code, suggestions),
    )


def _render_404_html(short_code: str, suggestions: list[str]) -> str:
    """Render the 404 HTML error page.

    Args:
        short_code: The short code that was not found.
        suggestions: List of suggested short codes.

    Returns:
        HTML string for the error page.
    """
    suggestions_html = ""
    if suggestions:
        links = "\n".join(
            f'        <li><a href="/{s}">{s}</a></li>' for s in suggestions
        )
        suggestions_html = f"""
    <p>Did you mean:</p>
    <ul>
{links}
    </ul>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Not Found</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Roboto, sans-serif;
            max-width: 600px;
            margin: 80px auto;
            padding: 0 20px;
            color: #333;
        }}
        h1 {{ color: #c0392b; }}
        a {{ color: #2980b9; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ margin: 8px 0; }}
        li a {{
            display: inline-block;
            padding: 6px 12px;
            background: #ecf0f1;
            border-radius: 4px;
        }}
        li a:hover {{ background: #d5dbdb; }}
        code {{ background: #f8f9fa; padding: 2px 6px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>404 &mdash; Not Found</h1>
    <p>The shortcut <code>{short_code}</code> does not exist.</p>{suggestions_html}
</body>
</html>"""


def _render_index_html(shortcuts: list[dict[str, str]]) -> str:
    """Render the index HTML page with search interface.

    Args:
        shortcuts: List of dicts with short_code and url keys.

    Returns:
        HTML string for the index page with search functionality.
    """
    import json

    shortcuts_json = json.dumps(shortcuts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Redirector</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Roboto, sans-serif;
            max-width: 600px;
            margin: 80px auto;
            padding: 0 20px;
            color: #333;
        }}
        h1 {{ color: #2c3e50; }}
        #search {{
            width: 100%;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #bdc3c7;
            border-radius: 6px;
            outline: none;
            box-sizing: border-box;
        }}
        #search:focus {{ border-color: #2980b9; }}
        #results {{
            max-height: 400px;
            overflow-y: auto;
            margin-top: 12px;
        }}
        .result {{
            display: block;
            padding: 10px 14px;
            border-bottom: 1px solid #ecf0f1;
            text-decoration: none;
            color: #333;
        }}
        .result:hover {{ background: #ecf0f1; }}
        .result-code {{
            font-weight: 600;
            color: #2980b9;
        }}
        .result-url {{
            font-size: 13px;
            color: #7f8c8d;
            margin-left: 8px;
        }}
        .empty {{ color: #95a5a6; padding: 20px 0; text-align: center; }}
    </style>
</head>
<body>
    <h1>Redirector</h1>
    <input type="text" id="search" placeholder="Type to search shortcuts..."
           autocomplete="off" autofocus>
    <div id="results"></div>
    <script>
        const shortcuts = {shortcuts_json};
        const searchInput = document.getElementById('search');
        const resultsDiv = document.getElementById('results');

        function truncate(str, max) {{
            return str.length > max ? str.substring(0, max) + '...' : str;
        }}

        function render(matches) {{
            if (matches.length === 0) {{
                resultsDiv.innerHTML = '<div class="empty">No matches found.</div>';
                return;
            }}
            resultsDiv.innerHTML = matches.map(function(s) {{
                return '<a class="result" href="/' + s.short_code + '">'
                    + '<span class="result-code">' + s.short_code + '</span>'
                    + '<span class="result-url">' + truncate(s.url, 60) + '</span>'
                    + '</a>';
            }}).join('');
        }}

        searchInput.addEventListener('input', function() {{
            const query = this.value.toLowerCase();
            if (!query) {{
                resultsDiv.innerHTML = '';
                return;
            }}
            const matches = shortcuts.filter(function(s) {{
                return s.short_code.includes(query);
            }});
            render(matches);
        }});
    </script>
</body>
</html>"""
