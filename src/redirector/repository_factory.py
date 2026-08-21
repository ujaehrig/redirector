"""Factory for creating the appropriate repository instance."""

from redirector.config import Settings
from redirector.repository import RedirectRepository, SqliteRedirectRepository
from redirector.repository_dynamodb import DynamoDbRedirectRepository


def create_repository(settings: Settings) -> RedirectRepository:
    """Create a repository instance based on the configuration.

    Args:
        settings: Application settings.

    Returns:
        A repository instance (SQLite or DynamoDB).
    """
    if settings.db_backend == "dynamodb":
        return DynamoDbRedirectRepository(
            table_name=settings.dynamodb_table,
            region=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url or None,
        )
    return SqliteRedirectRepository(settings.sqlite_path)
