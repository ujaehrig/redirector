"""Application configuration."""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    port: int = 8080
    db_backend: Literal["sqlite", "dynamodb"] = "sqlite"
    sqlite_path: str = "./redirects.db"
    dynamodb_table: str = "redirects"
    aws_region: str = "eu-central-1"

    # JWT Authentication
    jwks_url: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = ""
    jwt_groups_claim: str = "groups"
    admin_group: str = "admin"

    # CLI mode
    cli_mode: Literal["local", "api"] = "local"
    api_url: str = "http://localhost:8080"
    api_token: str = ""

    # 404 suggestions
    suggestion_threshold: float = 0.6
    max_suggestions: int = 5

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        """Validate port is in the valid range."""
        if v < 1 or v > 65535:
            msg = "Port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}
