"""Tests for the Lambda handler."""

import os
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import patch


def _get_handler(db_path: str) -> Any:
    """Create a fresh Lambda handler with the given DB path."""
    with (
        patch.dict(os.environ, {"SQLITE_PATH": db_path}, clear=True),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore", DeprecationWarning)
        from mangum import Mangum

        from redirector.main import create_application

        app = create_application()
        return Mangum(app)


class TestLambdaHandlerModule:
    """Test that the lambda_handler module is importable."""

    def test_module_exports_handler(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        with (
            patch.dict(os.environ, {"SQLITE_PATH": db_path}, clear=True),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", DeprecationWarning)
            import importlib

            import redirector.lambda_handler as lh

            importlib.reload(lh)
            assert callable(lh.handler)


class TestLambdaHandler:
    """Test the Mangum-wrapped Lambda handler."""

    def test_health_check(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        handler = _get_handler(db_path)

        event = {
            "version": "2.0",
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/health",
                    "sourceIp": "127.0.0.1",
                    "protocol": "HTTP/1.1",
                },
                "accountId": "123456789012",
                "apiId": "api-id",
                "stage": "$default",
                "requestId": "req-id",
                "time": "01/Jan/2024:00:00:00 +0000",
                "timeEpoch": 1704067200000,
                "domainName": "example.com",
                "domainPrefix": "example",
            },
            "rawPath": "/health",
            "rawQueryString": "",
            "headers": {},
            "isBase64Encoded": False,
        }

        result = handler(event, None)  # type: ignore[arg-type]
        assert result["statusCode"] == 200
        assert "ok" in result["body"]

    def test_redirect_not_found(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        handler = _get_handler(db_path)

        event = {
            "version": "2.0",
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/nonexistent",
                    "sourceIp": "127.0.0.1",
                    "protocol": "HTTP/1.1",
                },
                "accountId": "123456789012",
                "apiId": "api-id",
                "stage": "$default",
                "requestId": "req-id",
                "time": "01/Jan/2024:00:00:00 +0000",
                "timeEpoch": 1704067200000,
                "domainName": "example.com",
                "domainPrefix": "example",
            },
            "rawPath": "/nonexistent",
            "rawQueryString": "",
            "headers": {"accept": "application/json"},
            "isBase64Encoded": False,
        }

        result = handler(event, None)  # type: ignore[arg-type]
        assert result["statusCode"] == 404
        assert "not found" in result["body"]
