# Redirector

A minimal URL redirection service built with FastAPI and SQLite,
featuring group-based multi-tenancy and JWT authentication.

## Overview

Redirector provides a lightweight HTTP server that maps short codes to
destination URLs and responds with HTTP redirects. It supports
group-based access control where teams manage their own shortcuts
independently.

## Quick Start

```bash
# Install dependencies
uv sync

# Add some redirects (local mode)
uv run redirector-manage add heise https://www.heise.de --group engineering
uv run redirector-manage add google https://www.google.com --group engineering --public

# Start the server
uv run redirector
```

Then open `http://localhost:8080/heise` to be redirected to
`https://www.heise.de`.

## Endpoints

### Public (no auth required)

| Path            | Method | Description                              |
|-----------------|--------|------------------------------------------|
| `/`             | GET    | List all public redirects (JSON)         |
| `/health`       | GET    | Health check, returns `{"status": "ok"}` |
| `/favicon.ico`  | GET    | Returns 204 (no favicon)                 |
| `/{short_code}` | GET    | Redirect to destination or 404           |
| `/docs`         | GET    | OpenAPI documentation (Swagger UI)       |

### Authenticated (Bearer token required)

| Path                       | Method | Description                   |
|----------------------------|--------|-------------------------------|
| `/api/redirects`           | GET    | List user's group shortcuts   |
| `/api/redirects`           | POST   | Create a new redirect         |
| `/api/redirects/{code}`    | DELETE | Remove a redirect             |
| `/api/redirects/{code}`    | PATCH  | Enable/disable a redirect     |

## Multi-Tenancy

### Groups and Ownership

- Each redirect belongs to a **group** (the owner)
- A redirect can be marked **public** (visible to all in listings)
- Users see their own group's redirects plus all public ones
- Only the owning group (or admins) can modify a redirect
- Legacy entries (no group) are treated as public

### Authorization Rules

- Redirects work for anyone (no auth on the redirect path)
- `GET /` shows public shortcuts only
- `/api/redirects` endpoints require a valid JWT token
- Users can manage shortcuts in their own groups
- The `admin` group can manage any shortcut

### JWT Configuration

The app validates JWT tokens using JWKS. Configure via environment:

```bash
JWKS_URL=https://your-idp.example.com/.well-known/jwks.json
JWT_ISSUER=https://your-idp.example.com/
JWT_AUDIENCE=your-client-id
JWT_GROUPS_CLAIM=groups    # claim name containing group list
ADMIN_GROUP=admin          # group name with admin privileges
```

## CLI Management

### Local Mode (direct database access)

```bash
# Add a redirect with group ownership
uv run redirector-manage add mylink https://example.com --group engineering

# Add a public redirect
uv run redirector-manage add company https://company.com --group it --public

# List, disable, enable, remove
uv run redirector-manage list
uv run redirector-manage disable mylink
uv run redirector-manage enable mylink
uv run redirector-manage remove mylink
```

### API Mode (authenticated HTTP calls)

```bash
# Configure API mode
export CLI_MODE=api
export API_URL=http://localhost:8080
export API_TOKEN=your-jwt-token

# Same commands, now via the API
uv run redirector-manage list
uv run redirector-manage add mylink https://example.com --group engineering
uv run redirector-manage remove mylink
```

Or pass options directly:

```bash
uv run redirector-manage --mode api --api-url http://localhost:8080 --token YOUR_TOKEN list
```

### Short Code Rules

- Allowed characters: lowercase letters, digits, hyphens, underscores
- Length: 1-128 characters
- Case: automatically normalized to lowercase
- Reserved: `health` cannot be used as a short code

## Configuration

Configuration is loaded from environment variables with `.env` file
fallback. Copy `.env.example` to `.env` to get started.

| Variable           | Default          | Description                |
|--------------------|------------------|----------------------------|
| `PORT`             | `8080`           | Server listen port         |
| `DB_BACKEND`       | `sqlite`         | `sqlite` or `dynamodb`     |
| `SQLITE_PATH`      | `./redirects.db` | Path to SQLite database    |
| `DYNAMODB_TABLE`   | `redirects`      | DynamoDB table name        |
| `AWS_REGION`       | `eu-central-1`   | AWS region for DynamoDB    |
| `JWKS_URL`         |                  | JWKS endpoint URL          |
| `JWT_ISSUER`       |                  | Expected token issuer      |
| `JWT_AUDIENCE`     |                  | Expected token audience    |
| `JWT_GROUPS_CLAIM` | `groups`         | Token claim for groups     |
| `ADMIN_GROUP`      | `admin`          | Admin group name           |
| `CLI_MODE`         | `local`          | CLI mode: `local` or `api` |
| `API_URL`          | `localhost:8080` | API base URL (api mode)    |
| `API_TOKEN`        |                  | Bearer token (api mode)    |

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
├── auth.py           # JWT validation (JWKS, token decode, user)
├── repository.py     # Repository protocol + SQLite implementation
├── routes.py         # HTTP route handlers + API endpoints
└── cli.py            # CLI tool (click) with local/api modes
```

## Architecture

The app uses a **repository pattern** with a protocol interface,
making it straightforward to swap SQLite for DynamoDB when deploying
to AWS Lambda (via Mangum).

Authentication is handled via **JWT tokens** validated against a
JWKS endpoint. Group membership comes from a configurable token
claim, enabling any OIDC-compatible identity provider (Cognito,
Keycloak, Auth0, etc.).

## License

Private.
