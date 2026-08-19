"""Tests for the application entry point."""

import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI

from redirector.config import Settings
from redirector.main import create_application, main


class TestCreateApplication:
    """Test application factory."""

    def test_returns_fastapi_instance(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        settings = Settings(sqlite_path=db_path)
        app = create_application(settings)
        assert isinstance(app, FastAPI)

    def test_app_has_health_route(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        settings = Settings(sqlite_path=db_path)
        app = create_application(settings)
        routes: list[str] = [
            route.path  # type: ignore[attr-defined]
            for route in app.routes
        ]
        assert "/health" in routes

    def test_creates_settings_from_env_when_none(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"SQLITE_PATH": db_path}, clear=True):
            app = create_application()
        assert isinstance(app, FastAPI)


class TestMain:
    """Test the main entry point."""

    def test_main_calls_uvicorn_run(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        with (
            patch.dict(os.environ, {"SQLITE_PATH": db_path}, clear=True),
            patch("redirector.main.uvicorn.run") as mock_run,
        ):
            main()
        mock_run.assert_called_once_with(
            "redirector.main:app",
            host="0.0.0.0",
            port=8080,
            log_level="info",
        )

    def test_main_with_dynamodb_backend(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        with (
            patch.dict(
                os.environ,
                {"SQLITE_PATH": db_path, "DB_BACKEND": "dynamodb"},
                clear=True,
            ),
            patch("redirector.main.uvicorn.run") as mock_run,
        ):
            main()
        mock_run.assert_called_once()
