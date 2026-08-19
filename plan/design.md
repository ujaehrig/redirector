# Redirector App Design

## Overview

A minimal URL redirection service. The app provides an HTTP server that
looks up short codes from a database and responds with HTTP redirects to
the configured destination URL.

## Example

Database entry: `heise` → `https://www.heise.de`

Request: `GET /heise`
Response: `302 Found`, `Location: https://www.heise.de`

## Technology Stack

- **Language**: Python 3.12+
- **Package manager**: uv
- **Web framework**: FastAPI
- **ASGI server**: Uvicorn
- **Database (local)**: SQLite
- **Database (AWS)**: DynamoDB (deferred)
- **Lambda adapter**: Mangum (deferred)
- **Configuration**: pydantic-settings with `.env` fallback
- **Testing**: pytest + httpx (FastAPI TestClient)
- **Linting/Formatting**: ruff
- **Type checking**: pyright

## Architecture

### Repository Pattern

A `RedirectRepository` protocol defines the read interface. Concrete
implementations (SQLite now, DynamoDB later) fulfill the contract.

```python
class RedirectRepository(Protocol):
    def get_redirect(self, short_code: str) -> RedirectEntry | None: ...
```

### Data Model

Each redirect entry contains:

| Field             | Type     | Description                          |
|-------------------|----------|--------------------------------------|
| `short_code`      | str      | Primary key, 1-128 chars             |
| `destination_url` | str      | Target URL for the redirect          |
| `status_code`     | int      | HTTP status (301 or 302), default 302|
| `created_at`      | datetime | Timestamp of creation                |
| `enabled`         | bool     | Whether the redirect is active       |

### Short Code Validation Rules

- Allowed characters: `[a-z0-9_-]+`
- Length: 1–128 characters
- Case: normalized to lowercase on insert and lookup
- Reserved words: `health` (rejected on insert)

### HTTP Endpoints

| Path        | Method | Behavior                                    |
|-------------|--------|---------------------------------------------|
| `/health`   | GET    | Returns `200 {"status": "ok"}`              |
| `/{code}`   | GET    | Redirects or returns `404 {"error": "..."}` |

### Redirect Logic

1. Normalize incoming path to lowercase
2. Look up short code in repository
3. If found and enabled → respond with configured status code + Location
4. If found and disabled → respond 404
5. If not found → respond 404 with `{"error": "not found"}`

### Configuration

Loaded from environment variables with `.env` file fallback:

| Variable         | Default          | Description                |
|------------------|------------------|----------------------------|
| `PORT`           | `8080`           | Server listen port         |
| `DB_BACKEND`     | `sqlite`         | `sqlite` or `dynamodb`     |
| `SQLITE_PATH`    | `./redirects.db` | Path to SQLite database    |
| `DYNAMODB_TABLE` | `redirects`      | DynamoDB table name        |
| `AWS_REGION`     | `eu-central-1`   | AWS region for DynamoDB    |

### Logging

Standard Python `logging` at INFO level. Log each redirect request
(short code, destination, status) and errors (not found, DB failures).

### Caching

None. SQLite primary key lookups are sub-millisecond. DynamoDB
single-item gets are single-digit milliseconds. Caching can be added
later as a decorator on the repository method.

## Project Structure

```
redirector/
├── src/
│   └── redirector/
│       ├── __init__.py
│       ├── main.py          # FastAPI app, uvicorn entry point
│       ├── config.py        # pydantic-settings
│       ├── repository.py    # Protocol + SQLite implementation
│       └── routes.py        # Route handlers
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_repository.py
│   └── test_routes.py
├── plan/
│   ├── design.md
│   ├── development_approach.md
│   └── phase1_tasks.md
├── pyproject.toml
├── .env
└── .env.example
```

## Entry Points

- **Server**: `uv run redirector` → starts uvicorn on configured port
- **CLI**: `uv run redirector-manage` → manage redirect entries

### CLI Commands

- `add <short_code> <url> [--status 301|302]`
- `remove <short_code>`
- `list`
- `enable <short_code>`
- `disable <short_code>`

## Deferred (Out of Scope for Phase 1)

- Mangum / AWS Lambda adapter
- DynamoDB repository implementation
- Structured JSON logging
- Admin API endpoints
- Caching layer
