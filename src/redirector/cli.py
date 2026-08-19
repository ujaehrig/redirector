"""CLI management tool for redirect entries."""

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

import click
import httpx

RESERVED_PATHS = {"health"}
SHORT_CODE_PATTERN = re.compile(r"^[a-z0-9_-]+$")
MAX_SHORT_CODE_LENGTH = 128


def validate_short_code(short_code: str) -> str | None:
    """Validate a short code and return an error message or None.

    Args:
        short_code: The short code to validate.

    Returns:
        An error message if invalid, None if valid.
    """
    if not short_code or len(short_code) > MAX_SHORT_CODE_LENGTH:
        return (
            f"Invalid short code: must be between 1 and "
            f"{MAX_SHORT_CODE_LENGTH} characters"
        )
    if not SHORT_CODE_PATTERN.match(short_code):
        return (
            "Invalid short code: only lowercase alphanumeric, "
            "hyphens, and underscores allowed"
        )
    if short_code in RESERVED_PATHS:
        return f"Invalid short code: '{short_code}' is a reserved path"
    return None


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a database connection and ensure the table exists.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        An open database connection.
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS redirects (
            short_code TEXT PRIMARY KEY,
            destination_url TEXT NOT NULL,
            status_code INTEGER NOT NULL DEFAULT 302,
            created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            owner_group TEXT,
            public INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.commit()
    return conn


def _fail(message: str) -> None:
    """Print an error message and exit with code 1.

    Args:
        message: The error message to display.
    """
    click.echo(f"Error: {message}", err=True)
    raise SystemExit(1)


def _api_headers(token: str) -> dict[str, str]:
    """Build authorization headers for API requests.

    Args:
        token: The Bearer token.

    Returns:
        Headers dict with Authorization.
    """
    return {"Authorization": f"Bearer {token}"}


def _handle_api_error(response: httpx.Response) -> None:
    """Handle non-success API responses by printing error and exiting.

    Args:
        response: The httpx response to check.
    """
    if response.status_code >= 400:
        try:
            body = response.json()
            msg = body.get("error") or body.get("detail") or str(body)
        except Exception:
            msg = f"HTTP {response.status_code}"
        _fail(f"{response.status_code}: {msg}")


@click.group()
@click.option(
    "--db",
    default="./redirects.db",
    envvar="SQLITE_PATH",
    help="Path to the SQLite database (local mode).",
)
@click.option(
    "--mode",
    type=click.Choice(["local", "api"]),
    default="local",
    envvar="CLI_MODE",
    help="Operation mode: local (direct DB) or api (HTTP).",
)
@click.option(
    "--api-url",
    default="http://localhost:8080",
    envvar="API_URL",
    help="Base URL for the API (api mode).",
)
@click.option(
    "--token",
    default="",
    envvar="API_TOKEN",
    help="Bearer token for API authentication.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    db: str,
    mode: str,
    api_url: str,
    token: str,
) -> None:
    """Manage redirect entries."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db
    ctx.obj["mode"] = mode
    ctx.obj["api_url"] = api_url.rstrip("/")
    ctx.obj["token"] = token


@cli.command()
@click.argument("short_code")
@click.argument("url")
@click.option(
    "--status",
    type=int,
    default=302,
    help="HTTP status code (301 or 302).",
)
@click.option("--group", default=None, help="Owning group for the redirect.")
@click.option(
    "--public/--no-public",
    default=False,
    help="Make the redirect public.",
)
@click.pass_context
def add(
    ctx: click.Context,
    short_code: str,
    url: str,
    status: int,
    group: str | None,
    public: bool,
) -> None:
    """Add a new redirect entry."""
    normalized = short_code.lower()
    error = validate_short_code(normalized)
    if error:
        _fail(error)

    if ctx.obj["mode"] == "api":
        _add_api(ctx, normalized, url, status, group, public)
    else:
        _add_local(ctx, normalized, url, status, group, public)


def _add_api(
    ctx: click.Context,
    short_code: str,
    url: str,
    status: int,
    group: str | None,
    public: bool,
) -> None:
    """Add a redirect via the API."""
    payload: dict[str, Any] = {
        "short_code": short_code,
        "url": url,
        "status_code": status,
        "public": public,
    }
    if group:
        payload["group"] = group
    response = httpx.post(
        f"{ctx.obj['api_url']}/api/redirects",
        json=payload,
        headers=_api_headers(ctx.obj["token"]),
        timeout=10.0,
    )
    _handle_api_error(response)
    click.echo(f"Added: {short_code} -> {url} ({status})")


def _add_local(
    ctx: click.Context,
    short_code: str,
    url: str,
    status: int,
    group: str | None,
    public: bool,
) -> None:
    """Add a redirect directly to the local database."""
    conn = get_connection(ctx.obj["db_path"])
    try:
        existing = conn.execute(
            "SELECT short_code FROM redirects WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        if existing:
            _fail(f"Short code '{short_code}' already exists")

        now = datetime.now(tz=UTC).isoformat()
        conn.execute(
            "INSERT INTO redirects"
            " (short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public)"
            " VALUES (?, ?, ?, ?, 1, ?, ?)",
            (short_code, url, status, now, group, int(public)),
        )
        conn.commit()
        click.echo(f"Added: {short_code} -> {url} ({status})")
    finally:
        conn.close()


@cli.command()
@click.argument("short_code")
@click.pass_context
def remove(ctx: click.Context, short_code: str) -> None:
    """Remove a redirect entry."""
    normalized = short_code.lower()

    if ctx.obj["mode"] == "api":
        response = httpx.delete(
            f"{ctx.obj['api_url']}/api/redirects/{normalized}",
            headers=_api_headers(ctx.obj["token"]),
            timeout=10.0,
        )
        _handle_api_error(response)
        click.echo(f"Removed: {normalized}")
    else:
        conn = get_connection(ctx.obj["db_path"])
        try:
            cursor = conn.execute(
                "DELETE FROM redirects WHERE short_code = ?",
                (normalized,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                _fail(f"Short code '{normalized}' not found")
            click.echo(f"Removed: {normalized}")
        finally:
            conn.close()


@cli.command("list")
@click.pass_context
def list_entries(ctx: click.Context) -> None:
    """List all redirect entries."""
    if ctx.obj["mode"] == "api":
        response = httpx.get(
            f"{ctx.obj['api_url']}/api/redirects",
            headers=_api_headers(ctx.obj["token"]),
            timeout=10.0,
        )
        _handle_api_error(response)
        data = response.json()
        entries = data.get("redirects", [])
        if not entries:
            click.echo("No redirects configured.")
            return
        for entry in entries:
            status = "enabled" if entry.get("enabled") else "disabled"
            click.echo(
                f"  {entry['short_code']} -> {entry['url']}"
                f" ({entry['status_code']}) [{status}]"
            )
    else:
        conn = get_connection(ctx.obj["db_path"])
        try:
            rows = conn.execute(
                "SELECT short_code, destination_url,"
                " status_code, enabled"
                " FROM redirects ORDER BY short_code"
            ).fetchall()
            if not rows:
                click.echo("No redirects configured.")
                return
            for row in rows:
                status = "enabled" if row[3] else "disabled"
                click.echo(f"  {row[0]} -> {row[1]} ({row[2]}) [{status}]")
        finally:
            conn.close()


@cli.command()
@click.argument("short_code")
@click.pass_context
def disable(ctx: click.Context, short_code: str) -> None:
    """Disable a redirect entry."""
    normalized = short_code.lower()

    if ctx.obj["mode"] == "api":
        response = httpx.patch(
            f"{ctx.obj['api_url']}/api/redirects/{normalized}",
            json={"enabled": False},
            headers=_api_headers(ctx.obj["token"]),
            timeout=10.0,
        )
        _handle_api_error(response)
        click.echo(f"Disabled: {normalized}")
    else:
        conn = get_connection(ctx.obj["db_path"])
        try:
            cursor = conn.execute(
                "UPDATE redirects SET enabled = 0 WHERE short_code = ?",
                (normalized,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                _fail(f"Short code '{normalized}' not found")
            click.echo(f"Disabled: {normalized}")
        finally:
            conn.close()


@cli.command()
@click.argument("short_code")
@click.pass_context
def enable(ctx: click.Context, short_code: str) -> None:
    """Enable a redirect entry."""
    normalized = short_code.lower()

    if ctx.obj["mode"] == "api":
        response = httpx.patch(
            f"{ctx.obj['api_url']}/api/redirects/{normalized}",
            json={"enabled": True},
            headers=_api_headers(ctx.obj["token"]),
            timeout=10.0,
        )
        _handle_api_error(response)
        click.echo(f"Enabled: {normalized}")
    else:
        conn = get_connection(ctx.obj["db_path"])
        try:
            cursor = conn.execute(
                "UPDATE redirects SET enabled = 1 WHERE short_code = ?",
                (normalized,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                _fail(f"Short code '{normalized}' not found")
            click.echo(f"Enabled: {normalized}")
        finally:
            conn.close()


def main() -> None:
    """Entry point for the CLI tool."""
    cli()
