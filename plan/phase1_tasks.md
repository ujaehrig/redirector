# Phase 1 Tasks: Core Redirector

## Task 1: Project Initialization

Initialize the uv project with all required dependencies and configure
tooling.

**Steps:**

- Create `pyproject.toml` with project metadata and entry points
- Add dependencies: fastapi, uvicorn, pydantic-settings
- Add dev dependencies: pytest, pytest-cov, httpx, ruff, pyright
- Configure ruff, pyright, and pytest in `pyproject.toml`
- Create package structure with `__init__.py` files
- Create `.env.example`

**AI Prompt:** Initialize a Python project using uv with FastAPI,
uvicorn, pydantic-settings as runtime dependencies and pytest,
pytest-cov, httpx, ruff, pyright as dev dependencies. Configure entry
points `redirector` and `redirector-manage`. Set up src layout.

---

## Task 2: Configuration Module

Implement the settings model using pydantic-settings.

**Steps:**

- Write tests for config loading (defaults, env overrides)
- Implement `config.py` with `Settings` class
- Verify tests pass

**AI Prompt:** Create a pydantic-settings based configuration module
that loads PORT, DB_BACKEND, SQLITE_PATH, DYNAMODB_TABLE, and
AWS_REGION from environment variables with sensible defaults. Write
tests first.

---

## Task 3: Repository Layer

Implement the repository protocol and SQLite backend.

**Steps:**

- Write tests for `get_redirect` (found, not found, disabled entry)
- Write tests for SQLite table creation
- Define `RedirectEntry` dataclass
- Define `RedirectRepository` protocol
- Implement `SqliteRedirectRepository`
- Verify tests pass

**AI Prompt:** Implement a repository protocol with a `get_redirect`
method returning a `RedirectEntry` or None. Create an SQLite
implementation that auto-creates the table on init. Write all tests
first using in-memory SQLite.

---

## Task 4: HTTP Routes

Implement FastAPI route handlers.

**Steps:**

- Write tests for `GET /health` returning 200
- Write tests for `GET /{code}` returning 302 with Location header
- Write tests for `GET /{code}` returning 404 when not found
- Write tests for `GET /{code}` returning 404 when disabled
- Write tests for case normalization
- Implement `routes.py`
- Verify tests pass

**AI Prompt:** Implement FastAPI routes: `/health` returns 200 with
`{"status": "ok"}`, `/{code}` looks up the short code in the repository
and returns a redirect or 404. Use dependency injection for the
repository. Write all tests first using TestClient.

---

## Task 5: Application Entry Point

Wire everything together in `main.py`.

**Steps:**

- Create FastAPI app instance
- Configure dependency injection for repository
- Set up logging
- Create uvicorn runner for script entry point
- Verify app starts and serves redirects

**AI Prompt:** Create the FastAPI application entry point that loads
config, initializes the SQLite repository, registers routes, and starts
uvicorn. Ensure the `redirector` entry point works.

---

## Task 6: CLI Management Tool

Implement the command-line tool for managing redirect entries.

**Steps:**

- Write tests for add command (valid, invalid short code, reserved word)
- Write tests for remove command
- Write tests for list command
- Write tests for enable/disable commands
- Implement CLI using click or argparse
- Verify tests pass

**AI Prompt:** Implement a CLI tool with add, remove, list, enable, and
disable subcommands. Validate short codes against the rules (lowercase
alphanumeric + hyphens/underscores, 1-128 chars, no reserved words).
Write all tests first.

---

## Task 7: Integration and Polish

Final verification and cleanup.

**Steps:**

- Run `ruff format` on all files
- Run `ruff check` and fix any issues
- Run `pyright` and fix any type errors
- Run `pytest --cov` and verify 100% coverage
- Manual smoke test: start server, add entry via CLI, test redirect
- Update task file with completion markers

**AI Prompt:** Run all quality checks (ruff format, ruff check, pyright,
pytest with coverage). Fix any issues found. Perform a manual smoke test
of the full workflow.
