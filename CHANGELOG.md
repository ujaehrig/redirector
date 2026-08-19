# Changelog

All notable changes to this project will be documented in this file.

## [0.3.1] - 2026-08-19

### Changed

- `GET /` now returns a styled HTML page with a table of public
  shortcuts for browsers (content-negotiated, JSON still available
  via `Accept: application/json`)

## [0.3.0] - 2026-08-19

### Added

- Content-negotiated 404 error pages (HTML for browsers, JSON for APIs)
- Fuzzy shortcut suggestions on 404 (substring match + difflib fallback)
- Styled HTML error page with clickable suggestion links
- Configurable suggestion threshold (`SUGGESTION_THRESHOLD`, default 0.6)
- Configurable max suggestions (`MAX_SUGGESTIONS`, default 5)
- Only public shortcuts are used as suggestion candidates

## [0.2.0] - 2026-08-19

### Added

- JWT authentication with JWKS key fetching and caching
- Group-based multi-tenancy (shortcuts owned by groups)
- Public flag for company-wide shortcuts
- Authenticated management API (`/api/redirects`) with CRUD operations
- Authorization enforcement (group ownership or admin override)
- CLI dual mode: `local` (direct DB) and `api` (HTTP with Bearer token)
- `--group` and `--public` flags on the CLI `add` command
- Database migration for existing schemas (adds `owner_group`, `public`)
- OpenAPI documentation at `/docs`
- Configuration: `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`,
  `JWT_GROUPS_CLAIM`, `ADMIN_GROUP`, `CLI_MODE`, `API_URL`, `API_TOKEN`

### Changed

- `GET /` now returns only public shortcuts (was: all enabled)
- 404 JSON response includes `suggestions` field

## [0.1.0] - 2026-08-19

### Added

- FastAPI web server with URL redirection
- SQLite-backed repository with protocol interface
- `GET /health` endpoint
- `GET /favicon.ico` returns 204
- `GET /` lists available shortcuts
- `GET /{code}` redirects or returns 404
- Configurable redirect status (301/302, default 302)
- Short code validation (lowercase alphanumeric, hyphens, underscores)
- CLI tool (`redirector-manage`) for add/remove/list/enable/disable
- Configuration via environment variables with `.env` fallback
- pydantic-settings based configuration
- 100% test coverage
