"""Tests for the authenticated API management endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from redirector.auth import User
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
            0,
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
            "jira",
            "https://jira.example.com",
            302,
            "2024-01-15T13:00:00+00:00",
            1,
            "it",
            1,
        ),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        (
            "private-mkt",
            "https://marketing.example.com",
            302,
            "2024-01-15T15:00:00+00:00",
            1,
            "marketing",
            0,
        ),
    )
    conn.commit()
    return repo


def _make_client(
    repo: SqliteRedirectRepository, user: User | None = None
) -> TestClient:
    """Create a test client with optional authenticated user."""
    app = create_app(repo, user_override=user)
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def eng_user() -> User:
    """An engineering user."""
    return User(
        sub="user-1",
        email="eng@example.com",
        groups=["engineering"],
        is_admin=False,
    )


@pytest.fixture
def mkt_user() -> User:
    """A marketing user."""
    return User(
        sub="user-2",
        email="mkt@example.com",
        groups=["marketing"],
        is_admin=False,
    )


@pytest.fixture
def admin_user() -> User:
    """An admin user."""
    return User(
        sub="admin-1",
        email="admin@example.com",
        groups=["admin", "engineering"],
        is_admin=True,
    )


@pytest.fixture
def no_group_user() -> User:
    """A user with no groups."""
    return User(
        sub="user-3",
        email="nobody@example.com",
        groups=[],
        is_admin=False,
    )


class TestApiGetRedirects:
    """Test GET /api/redirects (authenticated listing)."""

    def test_returns_401_without_auth(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        client = _make_client(seeded_repo, user=None)
        response = client.get("/api/redirects")
        assert response.status_code == 401

    def test_returns_user_group_entries(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.get("/api/redirects")
        assert response.status_code == 200
        codes = [r["short_code"] for r in response.json()["redirects"]]
        assert "heise" in codes  # engineering, private
        assert "google" in codes  # engineering, public

    def test_includes_public_from_other_groups(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.get("/api/redirects")
        codes = [r["short_code"] for r in response.json()["redirects"]]
        assert "jira" in codes  # it group, but public

    def test_excludes_private_from_other_groups(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.get("/api/redirects")
        codes = [r["short_code"] for r in response.json()["redirects"]]
        assert "private-mkt" not in codes  # marketing, private

    def test_no_group_user_sees_only_public(
        self,
        seeded_repo: SqliteRedirectRepository,
        no_group_user: User,
    ) -> None:
        client = _make_client(seeded_repo, user=no_group_user)
        response = client.get("/api/redirects")
        codes = [r["short_code"] for r in response.json()["redirects"]]
        assert "google" in codes  # public
        assert "jira" in codes  # public
        assert "heise" not in codes  # private
        assert "private-mkt" not in codes  # private


class TestApiPostRedirects:
    """Test POST /api/redirects (create a redirect)."""

    def test_returns_401_without_auth(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        client = _make_client(seeded_repo, user=None)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "new",
                "url": "https://new.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 401

    def test_creates_redirect(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "new",
                "url": "https://new.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 201
        assert response.json()["short_code"] == "new"

    def test_returns_403_for_wrong_group(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "new",
                "url": "https://new.com",
                "group": "marketing",
            },
        )
        assert response.status_code == 403

    def test_admin_can_create_for_any_group(
        self,
        seeded_repo: SqliteRedirectRepository,
        admin_user: User,
    ) -> None:
        client = _make_client(seeded_repo, user=admin_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "admin-link",
                "url": "https://admin.com",
                "group": "marketing",
            },
        )
        assert response.status_code == 201

    def test_rejects_duplicate(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "heise",
                "url": "https://other.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 409

    def test_rejects_invalid_short_code(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "INVALID!",
                "url": "https://example.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 422

    def test_creates_with_public_flag(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "pub",
                "url": "https://pub.com",
                "group": "engineering",
                "public": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["public"] is True

    def test_creates_with_custom_status(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "perm",
                "url": "https://perm.com",
                "group": "engineering",
                "status_code": 301,
            },
        )
        assert response.status_code == 201
        assert response.json()["status_code"] == 301


class TestApiDeleteRedirect:
    """Test DELETE /api/redirects/{code}."""

    def test_returns_401_without_auth(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        client = _make_client(seeded_repo, user=None)
        response = client.delete("/api/redirects/heise")
        assert response.status_code == 401

    def test_deletes_own_group_entry(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.delete("/api/redirects/heise")
        assert response.status_code == 204

    def test_returns_403_for_other_group(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.delete("/api/redirects/private-mkt")
        assert response.status_code == 403

    def test_admin_can_delete_any(
        self,
        seeded_repo: SqliteRedirectRepository,
        admin_user: User,
    ) -> None:
        client = _make_client(seeded_repo, user=admin_user)
        response = client.delete("/api/redirects/private-mkt")
        assert response.status_code == 204

    def test_returns_404_for_nonexistent(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.delete("/api/redirects/nonexistent")
        assert response.status_code == 404


class TestApiPatchRedirect:
    """Test PATCH /api/redirects/{code}."""

    def test_returns_401_without_auth(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        client = _make_client(seeded_repo, user=None)
        response = client.patch("/api/redirects/heise", json={"enabled": False})
        assert response.status_code == 401

    def test_disables_own_group_entry(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.patch("/api/redirects/heise", json={"enabled": False})
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_enables_entry(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        # Disable first
        client.patch("/api/redirects/heise", json={"enabled": False})
        # Re-enable
        response = client.patch("/api/redirects/heise", json={"enabled": True})
        assert response.status_code == 200
        assert response.json()["enabled"] is True

    def test_returns_403_for_other_group(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.patch("/api/redirects/private-mkt", json={"enabled": False})
        assert response.status_code == 403

    def test_admin_can_patch_any(
        self,
        seeded_repo: SqliteRedirectRepository,
        admin_user: User,
    ) -> None:
        client = _make_client(seeded_repo, user=admin_user)
        response = client.patch("/api/redirects/private-mkt", json={"enabled": False})
        assert response.status_code == 200

    def test_returns_404_for_nonexistent(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.patch("/api/redirects/nonexistent", json={"enabled": False})
        assert response.status_code == 404

    def test_rejects_reserved_short_code(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "health",
                "url": "https://example.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 422

    def test_rejects_too_long_short_code(
        self, seeded_repo: SqliteRedirectRepository, eng_user: User
    ) -> None:
        client = _make_client(seeded_repo, user=eng_user)
        response = client.post(
            "/api/redirects",
            json={
                "short_code": "a" * 129,
                "url": "https://example.com",
                "group": "engineering",
            },
        )
        assert response.status_code == 422
