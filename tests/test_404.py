"""Tests for content-negotiated 404 with suggestions."""

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
    """Seed with public entries for suggestion matching."""
    conn = repo.connection
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "java17-api",
            "https://docs.oracle.com/en/java/javase/17/docs/api/",
            302,
            "2024-01-15T10:00:00+00:00",
            1,
            "engineering",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "java21-api",
            "https://docs.oracle.com/en/java/javase/21/docs/api/",
            302,
            "2024-01-15T10:00:00+00:00",
            1,
            "engineering",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "python-docs",
            "https://docs.python.org/3/",
            302,
            "2024-01-15T10:00:00+00:00",
            1,
            "engineering",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "private-tool",
            "https://internal.example.com",
            302,
            "2024-01-15T10:00:00+00:00",
            1,
            "engineering",
            0,
        ),
    )
    conn.commit()
    return repo


@pytest.fixture
def client(seeded_repo: SqliteRedirectRepository) -> TestClient:
    """Create a test client with seeded data."""
    app = create_app(
        seeded_repo,
        suggestion_threshold=0.6,
        max_suggestions=5,
    )
    return TestClient(app, follow_redirects=False)


class TestJsonNotFound:
    """Test JSON 404 responses with suggestions."""

    def test_returns_json_with_accept_header(self, client: TestClient) -> None:
        response = client.get("/java-api", headers={"Accept": "application/json"})
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"

    def test_includes_suggestions_in_json(self, client: TestClient) -> None:
        response = client.get("/java-api", headers={"Accept": "application/json"})
        body = response.json()
        assert "suggestions" in body
        assert "java17-api" in body["suggestions"]
        assert "java21-api" in body["suggestions"]

    def test_no_private_in_suggestions(self, client: TestClient) -> None:
        response = client.get("/private", headers={"Accept": "application/json"})
        body = response.json()
        assert "private-tool" not in body.get("suggestions", [])

    def test_empty_suggestions_when_no_match(self, client: TestClient) -> None:
        response = client.get("/xyzxyzxyz", headers={"Accept": "application/json"})
        body = response.json()
        assert body["suggestions"] == []

    def test_error_field_present(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={"Accept": "application/json"})
        body = response.json()
        assert body["error"] == "not found"


class TestHtmlNotFound:
    """Test HTML 404 responses with suggestions."""

    def test_returns_html_by_default(self, client: TestClient) -> None:
        response = client.get("/java-api")
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]

    def test_returns_html_with_accept_text_html(self, client: TestClient) -> None:
        response = client.get("/java-api", headers={"Accept": "text/html"})
        assert "text/html" in response.headers["content-type"]

    def test_returns_html_with_wildcard_accept(self, client: TestClient) -> None:
        response = client.get("/java-api", headers={"Accept": "*/*"})
        assert "text/html" in response.headers["content-type"]

    def test_html_contains_error_message(self, client: TestClient) -> None:
        response = client.get("/java-api")
        assert "not found" in response.text.lower()
        assert "java-api" in response.text

    def test_html_contains_suggestions_as_links(self, client: TestClient) -> None:
        response = client.get("/java-api")
        assert 'href="/java17-api"' in response.text
        assert 'href="/java21-api"' in response.text
        assert "java17-api" in response.text
        assert "java21-api" in response.text

    def test_html_no_suggestions_when_no_match(self, client: TestClient) -> None:
        response = client.get("/xyzxyzxyz")
        assert "xyzxyzxyz" in response.text
        assert "href=" not in response.text

    def test_html_does_not_suggest_private(self, client: TestClient) -> None:
        response = client.get("/private")
        assert "private-tool" not in response.text

    def test_html_has_inline_css(self, client: TestClient) -> None:
        response = client.get("/java-api")
        assert "<style>" in response.text


class TestContentNegotiation:
    """Test Accept header parsing."""

    def test_json_explicit(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={"Accept": "application/json"})
        assert response.headers["content-type"] == "application/json"

    def test_html_when_no_accept_header(self, client: TestClient) -> None:
        response = client.get("/nonexistent", headers={})
        assert "text/html" in response.headers["content-type"]

    def test_html_for_browser_accept(self, client: TestClient) -> None:
        # Typical browser Accept header
        response = client.get(
            "/nonexistent",
            headers={
                "Accept": "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            },
        )
        assert "text/html" in response.headers["content-type"]
