"""Tests for application version resolution."""

from pathlib import Path

import pytest

from redirector.routes import resolve_version


class TestResolveVersion:
    """Test the version resolution helper."""

    def test_falls_back_to_package_metadata_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("APP_VERSION_FILE", raising=False)
        # Package metadata version follows PEP 440 (starts with a digit).
        version = resolve_version()
        assert version
        assert version[0].isdigit()

    def test_reads_version_file_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        version_file = tmp_path / ".version"
        version_file.write_text("0.4.0+gabc1234\n")
        monkeypatch.setenv("APP_VERSION_FILE", str(version_file))
        assert resolve_version() == "0.4.0+gabc1234"

    def test_strips_whitespace_from_version_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        version_file = tmp_path / ".version"
        version_file.write_text("  1.2.3  \n")
        monkeypatch.setenv("APP_VERSION_FILE", str(version_file))
        assert resolve_version() == "1.2.3"

    def test_falls_back_when_version_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does-not-exist"
        monkeypatch.setenv("APP_VERSION_FILE", str(missing))
        version = resolve_version()
        assert version
        assert version[0].isdigit()

    def test_falls_back_when_version_file_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        version_file = tmp_path / ".version"
        version_file.write_text("   \n")
        monkeypatch.setenv("APP_VERSION_FILE", str(version_file))
        version = resolve_version()
        assert version
        assert version[0].isdigit()
