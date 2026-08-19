"""Repository protocol and implementations."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class RedirectEntry:
    """A single redirect mapping."""

    short_code: str
    destination_url: str
    status_code: int
    created_at: datetime
    enabled: bool
    owner_group: str | None = None
    public: bool = True


class RedirectRepository(Protocol):
    """Protocol defining the redirect repository interface."""

    def get_redirect(self, short_code: str) -> RedirectEntry | None:
        """Look up a redirect entry by short code.

        Args:
            short_code: The short code to look up.

        Returns:
            The redirect entry if found, None otherwise.
        """
        ...

    def list_redirects(self) -> list[RedirectEntry]:
        """List all enabled redirect entries.

        Returns:
            A list of enabled redirect entries, ordered by short code.
        """
        ...

    def list_public(self) -> list[RedirectEntry]:
        """List all enabled public redirect entries.

        Returns entries where public=1 or owner_group IS NULL,
        and enabled=1.

        Returns:
            A list of public redirect entries, ordered by short code.
        """
        ...

    def list_by_groups(self, groups: list[str]) -> list[RedirectEntry]:
        """List entries visible to the given groups.

        Returns entries where owner_group is in the given groups,
        OR public=1, OR owner_group IS NULL. Only enabled entries.

        Args:
            groups: List of group names the user belongs to.

        Returns:
            A list of redirect entries, ordered by short code.
        """
        ...

    def add_redirect(
        self,
        short_code: str,
        destination_url: str,
        status_code: int,
        owner_group: str | None,
        public: bool,
    ) -> RedirectEntry:
        """Add a new redirect entry.

        Args:
            short_code: The short code for the redirect.
            destination_url: The destination URL.
            status_code: HTTP status code (301 or 302).
            owner_group: The owning group, or None.
            public: Whether the redirect is visible to all.

        Returns:
            The created redirect entry.
        """
        ...

    def delete_redirect(self, short_code: str) -> bool:
        """Delete a redirect entry.

        Args:
            short_code: The short code to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    def set_enabled(self, short_code: str, *, enabled: bool) -> bool:
        """Enable or disable a redirect entry.

        Args:
            short_code: The short code to update.
            enabled: Whether to enable or disable.

        Returns:
            True if updated, False if not found.
        """
        ...


class SqliteRedirectRepository:
    """SQLite implementation of the redirect repository."""

    def __init__(self, db_path: str) -> None:
        """Initialize the repository and create the table if needed.

        Args:
            db_path: Path to the SQLite database file, or ":memory:".
        """
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
        self._migrate_schema()

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()

    def _create_table(self) -> None:
        """Create the redirects table if it does not exist."""
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS redirects (
                short_code TEXT PRIMARY KEY,
                destination_url TEXT NOT NULL,
                status_code INTEGER NOT NULL DEFAULT 302,
                created_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                owner_group TEXT,
                public INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.connection.commit()

    def _migrate_schema(self) -> None:
        """Add new columns to existing databases if missing."""
        cursor = self.connection.execute("PRAGMA table_info(redirects)")
        columns = {row[1] for row in cursor.fetchall()}

        if "owner_group" not in columns:
            self.connection.execute("ALTER TABLE redirects ADD COLUMN owner_group TEXT")
        if "public" not in columns:
            self.connection.execute(
                "ALTER TABLE redirects ADD COLUMN public INTEGER NOT NULL DEFAULT 1"
            )
        self.connection.commit()

    _RowType = tuple[str, str, int, str, int, str | None, int]

    def _row_to_entry(self, row: _RowType) -> RedirectEntry:
        """Convert a database row to a RedirectEntry."""
        return RedirectEntry(
            short_code=row[0],
            destination_url=row[1],
            status_code=row[2],
            created_at=datetime.fromisoformat(row[3]),
            enabled=bool(row[4]),
            owner_group=row[5],
            public=bool(row[6]),
        )

    def get_redirect(self, short_code: str) -> RedirectEntry | None:
        """Look up a redirect entry by short code.

        The lookup normalizes the short code to lowercase.

        Args:
            short_code: The short code to look up.

        Returns:
            The redirect entry if found, None otherwise.
        """
        normalized = short_code.lower()
        cursor = self.connection.execute(
            "SELECT short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public"
            " FROM redirects WHERE short_code = ?",
            (normalized,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_redirects(self) -> list[RedirectEntry]:
        """List all enabled redirect entries.

        Returns:
            A list of enabled redirect entries, ordered by short code.
        """
        cursor = self.connection.execute(
            "SELECT short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public"
            " FROM redirects WHERE enabled = 1"
            " ORDER BY short_code"
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def list_public(self) -> list[RedirectEntry]:
        """List all enabled public redirect entries.

        Returns entries where public=1 or owner_group IS NULL,
        and enabled=1.

        Returns:
            A list of public redirect entries, ordered by short code.
        """
        cursor = self.connection.execute(
            "SELECT short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public"
            " FROM redirects"
            " WHERE enabled = 1 AND (public = 1 OR owner_group IS NULL)"
            " ORDER BY short_code"
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def list_by_groups(self, groups: list[str]) -> list[RedirectEntry]:
        """List entries visible to the given groups.

        Returns entries where owner_group is in the given groups,
        OR public=1, OR owner_group IS NULL. Only enabled entries.

        Args:
            groups: List of group names the user belongs to.

        Returns:
            A list of redirect entries, ordered by short code.
        """
        if not groups:
            return self.list_public()

        placeholders = ",".join("?" for _ in groups)
        cursor = self.connection.execute(
            "SELECT short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public"
            " FROM redirects"
            " WHERE enabled = 1"
            f" AND (owner_group IN ({placeholders})"
            " OR public = 1 OR owner_group IS NULL)"
            " ORDER BY short_code",
            groups,
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def add_redirect(
        self,
        short_code: str,
        destination_url: str,
        status_code: int,
        owner_group: str | None,
        public: bool,
    ) -> RedirectEntry:
        """Add a new redirect entry.

        Args:
            short_code: The short code for the redirect.
            destination_url: The destination URL.
            status_code: HTTP status code (301 or 302).
            owner_group: The owning group, or None.
            public: Whether the redirect is visible to all.

        Returns:
            The created redirect entry.
        """
        now = datetime.now(tz=UTC).isoformat()
        self.connection.execute(
            "INSERT INTO redirects"
            " (short_code, destination_url, status_code,"
            " created_at, enabled, owner_group, public)"
            " VALUES (?, ?, ?, ?, 1, ?, ?)",
            (short_code, destination_url, status_code, now, owner_group, int(public)),
        )
        self.connection.commit()
        entry = self.get_redirect(short_code)
        assert entry is not None  # Just inserted, must exist
        return entry

    def delete_redirect(self, short_code: str) -> bool:
        """Delete a redirect entry.

        Args:
            short_code: The short code to delete.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self.connection.execute(
            "DELETE FROM redirects WHERE short_code = ?",
            (short_code,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def set_enabled(self, short_code: str, *, enabled: bool) -> bool:
        """Enable or disable a redirect entry.

        Args:
            short_code: The short code to update.
            enabled: Whether to enable or disable.

        Returns:
            True if updated, False if not found.
        """
        cursor = self.connection.execute(
            "UPDATE redirects SET enabled = ? WHERE short_code = ?",
            (int(enabled), short_code),
        )
        self.connection.commit()
        return cursor.rowcount > 0
