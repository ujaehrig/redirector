# Redirector

A minimal URL redirection service built with FastAPI and SQLite.

## Overview

Redirector provides a lightweight HTTP server that maps short codes to
destination URLs and responds with HTTP redirects. It is designed to run
locally with SQLite and can later be deployed to AWS Lambda with
DynamoDB.

## Quick Start

```bash
# Install dependencies
uv sync

# Add some redirects
uv run redirector-manage add heise https://www.heise.de
uv run redirector-manage add google https://www.google.com --status 301

# Start the server
uv run redirector
```

Then open `http://localhost:8080/heise` — you'll be redirected to
`https://www.heise.de`.

## Endpoints

| Path           | Method | Description                              |
|----------------|--------|------------------------------------------|
| `/`            | GET    | List all enabled redirects (JSON)        |
| `/health`      | GET    | Health check, returns `{"status": "ok"}` |
| `/favicon.ico` | GET    | Returns 204 (no favicon)                 |
| `/{short_code}`| GET    | Redirect to destination or 404           |

## CLI Management

Manage redirect entries with `uv run redirector-manage`:

```bash
# Add a redirect (default 302)
uv run redirector-manage add mylink https://example.com

# Add with permanent redirect (301)
uv run redirector-manage add mylink https://example.com --status 301

# List all entries
uv run redirector-manage list

# Disable a redirect (returns 404 without deleting)
uv run redirector-manage disable mylink

# Re-enable a redirect
uv run redirector-manage enable mylink

# Remove a redirect permanently
uv run redirector-manage remove mylink
```

### Short Code Rules

- Allowed characters: lowercase letters, digits, hyphens, underscores
- Length: 1-128 characters
- Case: automatically normalized to lowercase
- Reserved: `health` cannot be used as a short code

## Configuration

Configuration is loaded from environment variables with `.env` file
fallback. Copy `.env.example` to `.env` to get started.

| Variable         | Default          | Description              |
|------------------|------------------|--------------------------|
| `PORT`           | `8080`           | Server listen port       |
| `DB_BACKEND`     | `sqlite`         | `sqlite` or `dynamodb`   |
| `SQLITE_PATH`    | `./redirects.db` | Path to SQLite database  |
| `DYNAMODB_TABLE` | `redirects`      | DynamoDB table name      |
| `AWS_REGION`     | `eu-central-1`   | AWS region for DynamoDB  |

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests with coverage
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type checking
uv run pyright
```

## Project Structure

```
src/redirector/
├── __init__.py       # Package marker
├── main.py           # FastAPI app factory, uvicorn entry point
├── config.py         # Settings via pydantic-settings
├── repository.py     # Repository protocol + SQLite implementation
├── routes.py         # HTTP route handlers
└── cli.py            # CLI management tool (click)
```

## Architecture

The app uses a repository pattern with a protocol interface, making it
straightforward to swap SQLite for DynamoDB when deploying to AWS
Lambda (via Mangum).

## License

Private.
