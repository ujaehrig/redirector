# Phase 2 Tasks: Multi-Tenancy

## Task 1: Dependencies and Configuration

Add JWT-related dependencies and extend configuration.

**Steps:**

- Add dependencies: PyJWT, cryptography
- Add dev dependency: respx (for mocking HTTP in tests)
- Add config values: JWT_GROUPS_CLAIM, ADMIN_GROUP, JWT_ISSUER,
  JWT_AUDIENCE, JWKS_URL, CLI_MODE, API_URL, API_TOKEN
- Update .env.example

**AI Prompt:** Add PyJWT and cryptography as runtime dependencies.
Add respx as a dev dependency. Extend the Settings class with JWT
and CLI configuration values. Update .env.example.

---

## Task 2: JWT Auth Module

Implement JWT token validation with JWKS caching.

**Steps:**

- Write tests for JWKS fetching and caching
- Write tests for token validation (valid, expired, wrong issuer,
  wrong audience, missing groups claim)
- Write tests for user/groups extraction from token
- Implement auth module with JWKS cache, validation, and
  FastAPI dependency
- Verify tests pass

**AI Prompt:** Create an auth module that fetches JWKS keys,
validates JWT tokens (signature, exp, iss, aud), and extracts user
identity and group membership. Provide a FastAPI dependency that
returns the current user or raises 401. Write all tests first.

---

## Task 3: Database Migration

Add group and public columns to the redirects table.

**Steps:**

- Add `group` column (TEXT, nullable, NULL = legacy/public)
- Add `public` column (INTEGER, default 1 for legacy entries)
- Update SqliteRedirectRepository._create_table for new schemas
- Add migration logic for existing databases
- Write tests for migration

**AI Prompt:** Extend the redirects table with nullable `group`
(TEXT) and `public` (INTEGER, default 1) columns. Existing entries
get group=NULL and public=1. Write migration logic and tests.

---

## Task 4: Repository Updates

Extend repository with group-aware query methods.

**Steps:**

- Write tests for list_public (only public/legacy entries)
- Write tests for list_by_groups (entries matching user's groups
  plus public)
- Write tests for add_redirect with group and public fields
- Update RedirectRepository protocol
- Implement new methods in SqliteRedirectRepository
- Verify tests pass

**AI Prompt:** Extend the repository protocol with list_public,
list_by_groups, and add_redirect methods. Implement in SQLite.
list_public returns entries where public=1 or group IS NULL.
list_by_groups returns entries where group IN (user_groups) OR
public=1. Write all tests first.

---

## Task 5: API Management Endpoints

Implement authenticated CRUD endpoints.

**Steps:**

- Write tests for GET /api/redirects (returns user's scoped list)
- Write tests for POST /api/redirects (validates group membership)
- Write tests for DELETE /api/redirects/{code} (ownership check)
- Write tests for PATCH /api/redirects/{code} (enable/disable)
- Write tests for admin override on all operations
- Write tests for 401 on unauthenticated requests
- Implement endpoints
- Verify tests pass

**AI Prompt:** Implement RESTful management endpoints under /api/
that require JWT auth. GET lists user's shortcuts. POST creates
with group ownership. DELETE and PATCH require group ownership or
admin. Return 401 for unauthenticated, 403 for unauthorized.
Write all tests first.

---

## Task 6: Update Root Endpoint

Change GET / to return only public shortcuts.

**Steps:**

- Update route to call list_public instead of list_redirects
- Update existing tests
- Add test confirming non-public entries are excluded
- Verify tests pass

**AI Prompt:** Update GET / to use list_public so it only returns
shortcuts that are public or have no group (legacy). Update tests.

---

## Task 7: CLI Dual Mode

Add API mode to the CLI tool.

**Steps:**

- Write tests for CLI in local mode (existing behavior + group)
- Write tests for CLI in api mode (HTTP calls with auth)
- Add --group option to add command
- Add --public flag to add command
- Add CLI_MODE/API_URL/API_TOKEN config support
- Implement api mode using httpx
- Verify tests pass

**AI Prompt:** Extend the CLI to support two modes: local (direct
DB, current behavior with --group and --public flags) and api
(calls /api/redirects endpoints with Bearer token). Mode is
configured via CLI_MODE env var. Write all tests first.

---

## Task 8: OpenAPI Documentation

Add proper API documentation.

**Steps:**

- Add Pydantic request/response models for all API endpoints
- Add OAuth2 Bearer scheme to OpenAPI spec
- Add descriptions to all endpoints
- Verify /docs renders correctly

**AI Prompt:** Add Pydantic models for request/response bodies.
Configure FastAPI's OpenAPI schema with Bearer auth. Add
docstrings and descriptions to all endpoints. Verify /docs works.

---

## Task 9: Integration and Polish

Final verification and cleanup.

**Steps:**

- Run ruff format on all files
- Run ruff check and fix any issues
- Run pyright and fix any type errors
- Run pytest --cov and verify 100% coverage
- Update README with multi-tenancy docs
- Update phase2_tasks.md with completion markers

**AI Prompt:** Run all quality checks. Fix any issues. Update
README with auth and multi-tenancy documentation. Verify full
workflow with smoke test.
