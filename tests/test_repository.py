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
            "disabled",
            "https://example.com",
            302,
            "2024-01-15T12:00:00+00:00",
            0,
            "marketing",
            0,
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
            "legacy",
            "https://legacy.example.com",
            302,
            "2024-01-15T14:00:00+00:00",
            1,
            None,
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
            "owner_group",
            "public",
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
        assert result.owner_group == "engineering"
        assert result.public is False

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

    def test_returns_legacy_entry_with_null_group(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("legacy")
        assert result is not None
        assert result.owner_group is None
        assert result.public is True


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


class TestSqliteRedirectRepositoryListPublic:
    """Test the list_public method."""

    def test_returns_only_public_entries(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert "google" in codes  # public=1
        assert "jira" in codes  # public=1
        assert "legacy" in codes  # group=NULL, public=1
        assert "heise" not in codes  # public=0
        assert "private-mkt" not in codes  # public=0

    def test_excludes_disabled_entries(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert "disabled" not in codes

    def test_returns_empty_when_no_public(self, repo: SqliteRedirectRepository) -> None:
        results = repo.list_public()
        assert results == []

    def test_returns_ordered_by_short_code(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestSqliteRedirectRepositoryListByGroups:
    """Test the list_by_groups method."""

    def test_returns_entries_for_user_group(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "heise" in codes  # engineering, not public
        assert "google" in codes  # engineering, public

    def test_includes_public_entries_from_other_groups(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "jira" in codes  # it group, but public
        assert "legacy" in codes  # no group, public

    def test_excludes_private_entries_from_other_groups(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "private-mkt" not in codes  # marketing, not public

    def test_multiple_groups(self, seeded_repo: SqliteRedirectRepository) -> None:
        results = seeded_repo.list_by_groups(["engineering", "marketing"])
        codes = [r.short_code for r in results]
        assert "heise" in codes
        assert "private-mkt" in codes
        assert "jira" in codes  # public

    def test_excludes_disabled_entries(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["marketing"])
        codes = [r.short_code for r in results]
        assert "disabled" not in codes

    def test_empty_groups_returns_only_public(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups([])
        codes = [r.short_code for r in results]
        assert "google" in codes  # public
        assert "jira" in codes  # public
        assert "legacy" in codes  # public (null group)
        assert "heise" not in codes  # not public
        assert "private-mkt" not in codes  # not public

    def test_returns_ordered_by_short_code(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestSqliteRedirectRepositoryAddRedirect:
    """Test the add_redirect method."""

    def test_adds_entry_with_group(self, repo: SqliteRedirectRepository) -> None:
        repo.add_redirect(
            short_code="test",
            destination_url="https://example.com",
            status_code=302,
            owner_group="engineering",
            public=False,
        )
        result = repo.get_redirect("test")
        assert result is not None
        assert result.short_code == "test"
        assert result.destination_url == "https://example.com"
        assert result.owner_group == "engineering"
        assert result.public is False

    def test_adds_public_entry(self, repo: SqliteRedirectRepository) -> None:
        repo.add_redirect(
            short_code="public-link",
            destination_url="https://example.com",
            status_code=301,
            owner_group="it",
            public=True,
        )
        result = repo.get_redirect("public-link")
        assert result is not None
        assert result.public is True
        assert result.status_code == 301

    def test_sets_created_at(self, repo: SqliteRedirectRepository) -> None:
        repo.add_redirect(
            short_code="timed",
            destination_url="https://example.com",
            status_code=302,
            owner_group="engineering",
            public=False,
        )
        result = repo.get_redirect("timed")
        assert result is not None
        assert isinstance(result.created_at, datetime)

    def test_new_entry_is_enabled(self, repo: SqliteRedirectRepository) -> None:
        repo.add_redirect(
            short_code="enabled-test",
            destination_url="https://example.com",
            status_code=302,
            owner_group="engineering",
            public=False,
        )
        result = repo.get_redirect("enabled-test")
        assert result is not None
        assert result.enabled is True


class TestSqliteRedirectRepositoryDeleteRedirect:
    """Test the delete_redirect method."""

    def test_deletes_existing_entry(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        assert seeded_repo.delete_redirect("heise") is True
        assert seeded_repo.get_redirect("heise") is None

    def test_returns_false_for_nonexistent(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        assert seeded_repo.delete_redirect("nonexistent") is False


class TestSqliteRedirectRepositorySetEnabled:
    """Test the set_enabled method."""

    def test_disables_entry(self, seeded_repo: SqliteRedirectRepository) -> None:
        assert seeded_repo.set_enabled("heise", enabled=False) is True
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert result.enabled is False

    def test_enables_entry(self, seeded_repo: SqliteRedirectRepository) -> None:
        assert seeded_repo.set_enabled("disabled", enabled=True) is True
        result = seeded_repo.get_redirect("disabled")
        assert result is not None
        assert result.enabled is True

    def test_returns_false_for_nonexistent(
        self, seeded_repo: SqliteRedirectRepository
    ) -> None:
        assert seeded_repo.set_enabled("nonexistent", enabled=False) is False


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
            owner_group="engineering",
            public=False,
        )
        assert entry.short_code == "test"
        assert entry.destination_url == "https://example.com"
        assert entry.status_code == 302
        assert entry.created_at == now
        assert entry.enabled is True
        assert entry.owner_group == "engineering"
        assert entry.public is False

    def test_create_legacy_entry(self) -> None:
        now = datetime.now(tz=UTC)
        entry = RedirectEntry(
            short_code="legacy",
            destination_url="https://example.com",
            status_code=302,
            created_at=now,
            enabled=True,
            owner_group=None,
            public=True,
        )
        assert entry.owner_group is None
        assert entry.public is True


class TestSqliteRedirectRepositoryMigration:
    """Test database migration for existing databases."""

    def test_migrates_old_schema(self) -> None:
        """An existing DB without group/public columns gets migrated."""
        import sqlite3

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        # Create old schema
        conn.execute(
            """
            CREATE TABLE redirects (
                short_code TEXT PRIMARY KEY,
                destination_url TEXT NOT NULL,
                status_code INTEGER NOT NULL DEFAULT 302,
                created_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            "INSERT INTO redirects"
            " (short_code, destination_url, status_code,"
            " created_at, enabled)"
            " VALUES (?, ?, ?, ?, ?)",
            ("old", "https://old.com", 302, "2024-01-01T00:00:00+00:00", 1),
        )
        conn.commit()
        conn.close()

        # Re-open with our repository (triggers migration)
        # We can't use :memory: here since it's a new connection
        # Instead, test the migration method directly
        repo = SqliteRedirectRepository.__new__(SqliteRedirectRepository)
        repo.connection = sqlite3.connect(":memory:", check_same_thread=False)
        # Create old schema manually
        repo.connection.execute(
            """
            CREATE TABLE redirects (
                short_code TEXT PRIMARY KEY,
                destination_url TEXT NOT NULL,
                status_code INTEGER NOT NULL DEFAULT 302,
                created_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        repo.connection.execute(
            "INSERT INTO redirects"
            " (short_code, destination_url, status_code,"
            " created_at, enabled)"
            " VALUES (?, ?, ?, ?, ?)",
            ("old", "https://old.com", 302, "2024-01-01T00:00:00+00:00", 1),
        )
        repo.connection.commit()

        # Run migration
        repo._migrate_schema()  # pyright: ignore[reportPrivateUsage]

        # Verify columns exist and old data has defaults
        result = repo.connection.execute(
            "SELECT owner_group, public FROM redirects WHERE short_code = 'old'"
        ).fetchone()
        assert result is not None
        assert result[0] is None  # owner_group = NULL
        assert result[1] == 1  # public = 1 (legacy entries are public)
        repo.close()
