"""Repository protocol and implementations."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RedirectEntry:
    """A single redirect mapping."""

    short_code: str
    destination_url: str
    status_code: int
    created_at: datetime
    enabled: bool


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


class SqliteRedirectRepository:
    """SQLite implementation of the redirect repository."""

    def __init__(self, db_path: str) -> None:
        """Initialize the repository and create the table if needed.

        Args:
            db_path: Path to the SQLite database file, or ":memory:".
        """
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

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
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.connection.commit()

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
            "SELECT short_code, destination_url, status_code, created_at, enabled "
            "FROM redirects WHERE short_code = ?",
            (normalized,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return RedirectEntry(
            short_code=row[0],
            destination_url=row[1],
            status_code=row[2],
            created_at=datetime.fromisoformat(row[3]),
            enabled=bool(row[4]),
        )

    def list_redirects(self) -> list[RedirectEntry]:
        """List all enabled redirect entries.

        Returns:
            A list of enabled redirect entries, ordered by short code.
        """
        cursor = self.connection.execute(
            "SELECT short_code, destination_url, status_code,"
            " created_at, enabled"
            " FROM redirects WHERE enabled = 1"
            " ORDER BY short_code"
        )
        return [
            RedirectEntry(
                short_code=row[0],
                destination_url=row[1],
                status_code=row[2],
                created_at=datetime.fromisoformat(row[3]),
                enabled=bool(row[4]),
            )
            for row in cursor.fetchall()
        ]
