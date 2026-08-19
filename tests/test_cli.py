"""Tests for the CLI management tool."""

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from redirector.cli import cli

from .conftest import INSERT_REDIRECT_SQL


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Create a temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def seeded_db(db_path: str) -> str:
    """Create a database with some existing entries."""
    conn = sqlite3.connect(db_path)
    conn.execute(
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
    conn.execute(
        INSERT_REDIRECT_SQL,
        ("heise", "https://www.heise.de", 302, "2024-01-15T10:30:00+00:00", 1),
    )
    conn.execute(
        INSERT_REDIRECT_SQL,
        ("google", "https://www.google.com", 301, "2024-01-15T11:00:00+00:00", 1),
    )
    conn.commit()
    conn.close()
    return db_path


class TestCliAdd:
    """Test the add command."""

    def test_add_entry(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "heise", "https://www.heise.de"]
        )
        assert result.exit_code == 0
        assert "Added" in result.output

    def test_add_entry_with_custom_status(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = runner.invoke(
            cli,
            [
                "--db",
                db_path,
                "add",
                "heise",
                "https://www.heise.de",
                "--status",
                "301",
            ],
        )
        assert result.exit_code == 0
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT status_code FROM redirects WHERE short_code = ?", ("heise",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 301

    def test_add_normalizes_to_lowercase(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "HEISE", "https://www.heise.de"]
        )
        assert result.exit_code == 0
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT short_code FROM redirects WHERE short_code = ?", ("heise",)
        ).fetchone()
        conn.close()
        assert row is not None

    def test_add_rejects_invalid_characters(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "he!se", "https://www.heise.de"]
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output

    def test_add_rejects_spaces(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "he ise", "https://www.heise.de"]
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output

    def test_add_rejects_empty_code(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "", "https://www.heise.de"]
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output

    def test_add_rejects_too_long_code(self, runner: CliRunner, db_path: str) -> None:
        long_code = "a" * 129
        result = runner.invoke(
            cli, ["--db", db_path, "add", long_code, "https://www.heise.de"]
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output

    def test_add_rejects_reserved_word_health(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "health", "https://example.com"]
        )
        assert result.exit_code != 0
        assert "reserved" in result.output.lower()

    def test_add_rejects_duplicate(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(
            cli, ["--db", seeded_db, "add", "heise", "https://other.com"]
        )
        assert result.exit_code != 0
        assert "exists" in result.output.lower()

    def test_add_allows_hyphens_and_underscores(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = runner.invoke(
            cli, ["--db", db_path, "add", "my-cool_link", "https://example.com"]
        )
        assert result.exit_code == 0
        assert "Added" in result.output


class TestCliRemove:
    """Test the remove command."""

    def test_remove_existing_entry(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "remove", "heise"])
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_nonexistent_entry(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "remove", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestCliList:
    """Test the list command."""

    def test_list_entries(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "list"])
        assert result.exit_code == 0
        assert "heise" in result.output
        assert "google" in result.output

    def test_list_empty_database(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(cli, ["--db", db_path, "list"])
        assert result.exit_code == 0
        assert "No redirects" in result.output


class TestCliDisable:
    """Test the disable command."""

    def test_disable_entry(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "disable", "heise"])
        assert result.exit_code == 0
        assert "Disabled" in result.output

    def test_disable_nonexistent(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "disable", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestCliEnable:
    """Test the enable command."""

    def test_enable_entry(self, runner: CliRunner, seeded_db: str) -> None:
        # First disable, then enable
        runner.invoke(cli, ["--db", seeded_db, "disable", "heise"])
        result = runner.invoke(cli, ["--db", seeded_db, "enable", "heise"])
        assert result.exit_code == 0
        assert "Enabled" in result.output

    def test_enable_nonexistent(self, runner: CliRunner, seeded_db: str) -> None:
        result = runner.invoke(cli, ["--db", seeded_db, "enable", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestCliMain:
    """Test the main entry point."""

    def test_main_invokes_cli(self) -> None:
        """Test that main() calls cli() which shows help with --help."""
        from unittest.mock import patch

        from redirector.cli import main

        with patch("sys.argv", ["redirector-manage", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
