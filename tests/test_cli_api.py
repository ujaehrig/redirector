"""Tests for the CLI tool in API mode."""

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from click.testing import CliRunner

from redirector.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    """Create a mock httpx response."""
    request = httpx.Request("GET", "http://test")
    return httpx.Response(
        status_code,
        json=json_data or {},
        request=request,
    )


class TestCliApiModeList:
    """Test list command in API mode."""

    def test_lists_redirects_from_api(self, runner: CliRunner) -> None:
        response_data = {
            "redirects": [
                {
                    "short_code": "heise",
                    "url": "https://www.heise.de",
                    "status_code": 302,
                    "owner_group": "engineering",
                    "public": False,
                    "enabled": True,
                },
            ]
        }
        with patch("redirector.cli.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "my-token",
                    "list",
                ],
            )
        assert result.exit_code == 0
        assert "heise" in result.output
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "Authorization" in call_kwargs.kwargs["headers"]

    def test_list_empty(self, runner: CliRunner) -> None:
        response_data: dict[str, Any] = {"redirects": []}
        with patch("redirector.cli.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(200, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "list",
                ],
            )
        assert result.exit_code == 0
        assert "No redirects" in result.output

    def test_list_401_shows_error(self, runner: CliRunner) -> None:
        with patch("redirector.cli.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(
                401, {"detail": "Authentication required"}
            )
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "bad",
                    "list",
                ],
            )
        assert result.exit_code != 0
        assert "401" in result.output or "Authentication" in result.output


class TestCliApiModeAdd:
    """Test add command in API mode."""

    def test_adds_redirect_via_api(self, runner: CliRunner) -> None:
        response_data = {
            "short_code": "new",
            "url": "https://new.com",
            "status_code": 302,
            "owner_group": "engineering",
            "public": False,
            "enabled": True,
        }
        with patch("redirector.cli.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(201, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "add",
                    "new",
                    "https://new.com",
                    "--group",
                    "engineering",
                ],
            )
        assert result.exit_code == 0
        assert "Added" in result.output

    def test_add_409_shows_error(self, runner: CliRunner) -> None:
        with patch("redirector.cli.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(
                409, {"error": "Short code 'heise' already exists"}
            )
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "add",
                    "heise",
                    "https://other.com",
                    "--group",
                    "engineering",
                ],
            )
        assert result.exit_code != 0
        assert "exists" in result.output.lower()

    def test_add_403_shows_error(self, runner: CliRunner) -> None:
        with patch("redirector.cli.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(
                403, {"error": "Not a member of the target group"}
            )
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "add",
                    "new",
                    "https://new.com",
                    "--group",
                    "marketing",
                ],
            )
        assert result.exit_code != 0
        assert "403" in result.output or "member" in result.output.lower()


class TestCliApiModeRemove:
    """Test remove command in API mode."""

    def test_removes_redirect_via_api(self, runner: CliRunner) -> None:
        with patch("redirector.cli.httpx.delete") as mock_delete:
            mock_delete.return_value = _mock_response(204)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "remove",
                    "heise",
                ],
            )
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_404_shows_error(self, runner: CliRunner) -> None:
        with patch("redirector.cli.httpx.delete") as mock_delete:
            mock_delete.return_value = _mock_response(404, {"error": "not found"})
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "remove",
                    "nonexistent",
                ],
            )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestCliApiModeDisable:
    """Test disable command in API mode."""

    def test_disables_via_api(self, runner: CliRunner) -> None:
        response_data = {
            "short_code": "heise",
            "url": "https://www.heise.de",
            "status_code": 302,
            "owner_group": "engineering",
            "public": False,
            "enabled": False,
        }
        with patch("redirector.cli.httpx.patch") as mock_patch:
            mock_patch.return_value = _mock_response(200, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "disable",
                    "heise",
                ],
            )
        assert result.exit_code == 0
        assert "Disabled" in result.output


class TestCliApiModeEnable:
    """Test enable command in API mode."""

    def test_enables_via_api(self, runner: CliRunner) -> None:
        response_data = {
            "short_code": "heise",
            "url": "https://www.heise.de",
            "status_code": 302,
            "owner_group": "engineering",
            "public": False,
            "enabled": True,
        }
        with patch("redirector.cli.httpx.patch") as mock_patch:
            mock_patch.return_value = _mock_response(200, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "enable",
                    "heise",
                ],
            )
        assert result.exit_code == 0
        assert "Enabled" in result.output


class TestCliApiModeErrorHandling:
    """Test error handling for non-JSON API responses."""

    def test_handles_non_json_error_response(self, runner: CliRunner) -> None:
        request = httpx.Request("GET", "http://test")
        response = httpx.Response(500, text="Internal Server Error", request=request)
        with patch("redirector.cli.httpx.get") as mock_get:
            mock_get.return_value = response
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "list",
                ],
            )
        assert result.exit_code != 0
        assert "500" in result.output

    def test_add_without_group(self, runner: CliRunner) -> None:
        """Test add in API mode without specifying a group."""
        response_data = {
            "short_code": "nogroup",
            "url": "https://nogroup.com",
            "status_code": 302,
            "owner_group": None,
            "public": False,
            "enabled": True,
        }
        with patch("redirector.cli.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(201, response_data)
            result = runner.invoke(
                cli,
                [
                    "--mode",
                    "api",
                    "--api-url",
                    "http://localhost:8080",
                    "--token",
                    "t",
                    "add",
                    "nogroup",
                    "https://nogroup.com",
                ],
            )
        assert result.exit_code == 0
        # Verify group was not included in payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        assert "group" not in payload
