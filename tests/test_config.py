"""Tests for the configuration module."""

import os
from unittest.mock import patch

import pytest

from redirector.config import Settings


class TestSettingsDefaults:
    """Test that default values are applied correctly."""

    def test_default_port(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.port == 8080

    def test_default_db_backend(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.db_backend == "sqlite"

    def test_default_sqlite_path(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.sqlite_path == "./redirects.db"

    def test_default_dynamodb_table(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.dynamodb_table == "redirects"

    def test_default_aws_region(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.aws_region == "eu-central-1"


class TestSettingsFromEnvironment:
    """Test that environment variables override defaults."""

    def test_port_from_env(self) -> None:
        with patch.dict(os.environ, {"PORT": "9090"}, clear=True):
            settings = Settings()
        assert settings.port == 9090

    def test_db_backend_from_env(self) -> None:
        with patch.dict(os.environ, {"DB_BACKEND": "dynamodb"}, clear=True):
            settings = Settings()
        assert settings.db_backend == "dynamodb"

    def test_sqlite_path_from_env(self) -> None:
        with patch.dict(os.environ, {"SQLITE_PATH": "/tmp/test.db"}, clear=True):
            settings = Settings()
        assert settings.sqlite_path == "/tmp/test.db"

    def test_dynamodb_table_from_env(self) -> None:
        with patch.dict(os.environ, {"DYNAMODB_TABLE": "my-redirects"}, clear=True):
            settings = Settings()
        assert settings.dynamodb_table == "my-redirects"

    def test_aws_region_from_env(self) -> None:
        with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}, clear=True):
            settings = Settings()
        assert settings.aws_region == "us-west-2"


class TestSettingsValidation:
    """Test configuration validation."""

    def test_port_must_be_positive(self) -> None:
        with (
            patch.dict(os.environ, {"PORT": "0"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

    def test_port_must_be_valid_range(self) -> None:
        with (
            patch.dict(os.environ, {"PORT": "70000"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

    def test_db_backend_must_be_valid(self) -> None:
        with (
            patch.dict(os.environ, {"DB_BACKEND": "mysql"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

    def test_db_backend_sqlite_is_valid(self) -> None:
        with patch.dict(os.environ, {"DB_BACKEND": "sqlite"}, clear=True):
            settings = Settings()
        assert settings.db_backend == "sqlite"

    def test_db_backend_dynamodb_is_valid(self) -> None:
        with patch.dict(os.environ, {"DB_BACKEND": "dynamodb"}, clear=True):
            settings = Settings()
        assert settings.db_backend == "dynamodb"


class TestSettingsJwtDefaults:
    """Test JWT configuration defaults."""

    def test_default_jwks_url(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.jwks_url == ""

    def test_default_jwt_issuer(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.jwt_issuer == ""

    def test_default_jwt_audience(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.jwt_audience == ""

    def test_default_jwt_groups_claim(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.jwt_groups_claim == "groups"

    def test_default_admin_group(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.admin_group == "admin"


class TestSettingsCliDefaults:
    """Test CLI configuration defaults."""

    def test_default_cli_mode(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.cli_mode == "local"

    def test_default_api_url(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.api_url == "http://localhost:8080"

    def test_default_api_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.api_token == ""

    def test_cli_mode_from_env(self) -> None:
        with patch.dict(os.environ, {"CLI_MODE": "api"}, clear=True):
            settings = Settings()
        assert settings.cli_mode == "api"

    def test_cli_mode_must_be_valid(self) -> None:
        with (
            patch.dict(os.environ, {"CLI_MODE": "invalid"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()


class TestSettingsSuggestionDefaults:
    """Test suggestion configuration defaults."""

    def test_default_suggestion_threshold(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.suggestion_threshold == 0.6

    def test_default_max_suggestions(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.max_suggestions == 5

    def test_suggestion_threshold_from_env(self) -> None:
        with patch.dict(os.environ, {"SUGGESTION_THRESHOLD": "0.8"}, clear=True):
            settings = Settings()
        assert settings.suggestion_threshold == 0.8

    def test_max_suggestions_from_env(self) -> None:
        with patch.dict(os.environ, {"MAX_SUGGESTIONS": "10"}, clear=True):
            settings = Settings()
        assert settings.max_suggestions == 10
