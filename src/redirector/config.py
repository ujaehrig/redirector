"""Application configuration."""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    port: int = 8080
    db_backend: Literal["sqlite", "dynamodb"] = "sqlite"
    sqlite_path: str = "./redirects.db"
    dynamodb_table: str = "redirects"
    aws_region: str = "eu-central-1"

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v: int) -> int:
        """Validate port is in the valid range."""
        if v < 1 or v > 65535:
            msg = "Port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}
