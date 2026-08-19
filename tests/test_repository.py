"""Tests for the repository layer."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest

from redirector.repository import RedirectEntry, SqliteRedirectRepository

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
        ("heise", "https://www.heise.de", 302, "2024-01-15T10:30:00+00:00", 1),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        ("google", "https://www.google.com", 301, "2024-01-15T11:00:00+00:00", 1),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        ("disabled", "https://example.com", 302, "2024-01-15T12:00:00+00:00", 0),
    )
    conn.commit()
    return repo


class TestSqliteRedirectRepositoryInit:
    """Test repository initialization and table creation."""

    def test_creates_table_on_init(self, repo: SqliteRedirectRepository) -> None:
        cursor = repo.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='redirects'"
        )
        assert cursor.fetchone() is not None

    def test_table_has_correct_columns(self, repo: SqliteRedirectRepository) -> None:
        cursor = repo.connection.execute("PRAGMA table_info(redirects)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "short_code",
            "destination_url",
            "status_code",
            "created_at",
            "enabled",
        }
        assert columns == expected

    def test_short_code_is_primary_key(self, repo: SqliteRedirectRepository) -> None:
        cursor = repo.connection.execute("PRAGMA table_info(redirects)")
        for row in cursor.fetchall():
            if row[1] == "short_code":
                assert row[5] == 1  # pk column


class TestSqliteRedirectRepositoryGetRedirect:
    """Test the get_redirect method."""

    def test_returns_entry_when_found(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert result.short_code == "heise"
        assert result.destination_url == "https://www.heise.de"
        assert result.status_code == 302
        assert result.enabled is True

    def test_returns_none_when_not_found(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("nonexistent")
        assert result is None

    def test_returns_disabled_entry(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("disabled")
        assert result is not None
        assert result.enabled is False

    def test_returns_entry_with_301_status(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("google")
        assert result is not None
        assert result.status_code == 301

    def test_returns_entry_with_created_at(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert isinstance(result.created_at, datetime)

    def test_lookup_is_case_insensitive(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("HEISE")
        assert result is not None
        assert result.short_code == "heise"

    def test_lookup_normalizes_mixed_case(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("Heise")
        assert result is not None
        assert result.short_code == "heise"


class TestSqliteRedirectRepositoryListRedirects:
    """Test the list_redirects method."""

    def test_returns_only_enabled_entries(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_redirects()
        codes = [r.short_code for r in results]
        assert "heise" in codes
        assert "google" in codes
        assert "disabled" not in codes

    def test_returns_empty_list_when_no_entries(
        self, repo: SqliteRedirectRepository
    ) -> None:
        results = repo.list_redirects()
        assert results == []

    def test_returns_entries_ordered_by_short_code(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_redirects()
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestRedirectEntry:
    """Test the RedirectEntry dataclass."""

    def test_create_entry(self) -> None:
        now = datetime.now(tz=UTC)
        entry = RedirectEntry(
            short_code="test",
            destination_url="https://example.com",
            status_code=302,
            created_at=now,
            enabled=True,
        )
        assert entry.short_code == "test"
        assert entry.destination_url == "https://example.com"
        assert entry.status_code == 302
        assert entry.created_at == now
        assert entry.enabled is True
