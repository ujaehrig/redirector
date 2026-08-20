"""Tests for HTTP route handlers."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from redirector.repository import SqliteRedirectRepository
from redirector.routes import create_app

from .conftest import INSERT_REDIRECT_SQL


@pytest.fixture
def repo() -> Generator[SqliteRedirectRepository, None, None]:
    """Create an in-memory SQLite repository for testing."""
    repository = SqliteRedirectRepository(":memory:")
    yield repository
    repository.close()


@pytest.fixture
def seeded_repo(repo: SqliteRedirectRepository) -> SqliteRedirectRepository:
    """Create a repository with pre-seeded test data."""
    conn = repo.connection
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "heise",
            "https://www.heise.de",
            302,
            "2024-01-15T10:30:00+00:00",
            1,
            "engineering",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "google",
            "https://www.google.com",
            301,
            "2024-01-15T11:00:00+00:00",
            1,
            "engineering",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "disabled",
            "https://example.com",
            302,
            "2024-01-15T12:00:00+00:00",
            0,
            "marketing",
            0,
        ),
    )
    conn.commit()
    return repo


@pytest.fixture
def client(seeded_repo: SqliteRedirectRepository) -> TestClient:
    """Create a test client with a seeded repository."""
    app = create_app(seeded_repo)
    return TestClient(app, follow_redirects=False)


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_status_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body


class TestFaviconEndpoint:
    """Test the /favicon.ico endpoint."""

    def test_returns_204(self, client: TestClient) -> None:
        response = client.get("/favicon.ico")
        assert response.status_code == 204

    def test_returns_empty_body(self, client: TestClient) -> None:
        response = client.get("/favicon.ico")
        assert response.content == b""


class TestRootEndpoint:
    """Test the / endpoint listing available redirects."""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_returns_html_by_default(self, client: TestClient) -> None:
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_returns_json_with_accept_header(self, client: TestClient) -> None:
        response = client.get("/", headers={"Accept": "application/json"})
        body = response.json()
        assert "redirects" in body

    def test_lists_enabled_redirects(self, client: TestClient) -> None:
        response = client.get("/", headers={"Accept": "application/json"})
        body = response.json()
        codes = [r["short_code"] for r in body["redirects"]]
        assert "heise" in codes
        assert "google" in codes

    def test_excludes_disabled_redirects(self, client: TestClient) -> None:
        response = client.get("/", headers={"Accept": "application/json"})
        body = response.json()
        codes = [r["short_code"] for r in body["redirects"]]
        assert "disabled" not in codes

    def test_includes_url_in_entries(self, client: TestClient) -> None:
        response = client.get("/", headers={"Accept": "application/json"})
        body = response.json()
        heise = next(r for r in body["redirects"] if r["short_code"] == "heise")
        assert heise["url"] == "https://www.heise.de"

    def test_html_contains_shortcut_links(self, client: TestClient) -> None:
        response = client.get("/")
        # Shortcuts are embedded as JSON for client-side filtering
        assert '"short_code": "heise"' in response.text
        assert '"short_code": "google"' in response.text

    def test_html_has_search_input(self, client: TestClient) -> None:
        response = client.get("/")
        assert 'id="search"' in response.text
        assert "placeholder" in response.text

    def test_html_has_inline_css(self, client: TestClient) -> None:
        response = client.get("/")
        assert "<style>" in response.text

    def test_html_has_javascript(self, client: TestClient) -> None:
        response = client.get("/")
        assert "<script>" in response.text

    def test_html_shows_empty_page_when_no_shortcuts(self) -> None:
        from redirector.repository import SqliteRedirectRepository
        from redirector.routes import create_app

        repo = SqliteRedirectRepository(":memory:")
        app = create_app(repo)
        empty_client = TestClient(app, follow_redirects=False)
        response = empty_client.get("/")
        # Should still render the search UI with empty data
        assert 'id="search"' in response.text
        assert "shortcuts = []" in response.text
        repo.close()


class TestRedirectEndpoint:
    """Test the redirect endpoint."""

    def test_redirects_with_302(self, client: TestClient) -> None:
        response = client.get("/heise")
        assert response.status_code == 302
        assert response.headers["location"] == "https://www.heise.de"

    def test_redirects_with_301(self, client: TestClient) -> None:
        response = client.get("/google")
        assert response.status_code == 301
        assert response.headers["location"] == "https://www.google.com"

    def test_returns_404_when_not_found(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={"Accept": "application/json"})
        assert response.status_code == 404
        assert response.json()["error"] == "not found"

    def test_returns_404_when_disabled(self, client: TestClient) -> None:
        response = client.get("/disabled", headers={"Accept": "application/json"})
        assert response.status_code == 404
        assert response.json()["error"] == "not found"

    def test_normalizes_case(self, client: TestClient) -> None:
        response = client.get("/HEISE")
        assert response.status_code == 302
        assert response.headers["location"] == "https://www.heise.de"

    def test_normalizes_mixed_case(self, client: TestClient) -> None:
        response = client.get("/Heise")
        assert response.status_code == 302
        assert response.headers["location"] == "https://www.heise.de"


class TestNotFoundResponse:
    """Test 404 response format."""

    def test_content_type_is_json(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={"Accept": "application/json"})
        assert response.headers["content-type"] == "application/json"

    def test_body_has_error_key(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={"Accept": "application/json"})
        body = response.json()
        assert "error" in body
        assert body["error"] == "not found"
