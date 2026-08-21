"""Tests for the repository factory."""

import os
from unittest.mock import patch

import boto3
from moto import mock_aws

from redirector.config import Settings
from redirector.repository import SqliteRedirectRepository
from redirector.repository_dynamodb import DynamoDbRedirectRepository
from redirector.repository_factory import create_repository


class TestRepositoryFactory:
    """Test create_repository function."""

    def test_creates_sqlite_by_default(self, tmp_path) -> None:
        db_path = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"SQLITE_PATH": db_path}, clear=True):
            settings = Settings()
        repo = create_repository(settings)
        assert isinstance(repo, SqliteRedirectRepository)
        repo.close()

    def test_creates_dynamodb_when_configured(self) -> None:
        with mock_aws():
            client = boto3.client("dynamodb", region_name="eu-central-1")
            client.create_table(
                TableName="test-table",
                KeySchema=[{"AttributeName": "short_code", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "short_code", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            with patch.dict(
                os.environ,
                {
                    "DB_BACKEND": "dynamodb",
                    "DYNAMODB_TABLE": "test-table",
                    "AWS_REGION": "eu-central-1",
                },
                clear=True,
            ):
                settings = Settings()
            repo = create_repository(settings)
            assert isinstance(repo, DynamoDbRedirectRepository)

    def test_passes_endpoint_url_for_dynamodb(self) -> None:
        with mock_aws():
            client = boto3.client("dynamodb", region_name="eu-central-1")
            client.create_table(
                TableName="test-table",
                KeySchema=[{"AttributeName": "short_code", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "short_code", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            with patch.dict(
                os.environ,
                {
                    "DB_BACKEND": "dynamodb",
                    "DYNAMODB_TABLE": "test-table",
                    "AWS_REGION": "eu-central-1",
                    "DYNAMODB_ENDPOINT_URL": "http://localhost:8000",
                },
                clear=True,
            ):
                settings = Settings()
            repo = create_repository(settings)
            assert isinstance(repo, DynamoDbRedirectRepository)
