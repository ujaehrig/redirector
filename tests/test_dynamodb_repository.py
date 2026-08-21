"""Tests for the DynamoDB repository implementation."""

from datetime import datetime

import boto3
import pytest
from moto import mock_aws

from redirector.repository_dynamodb import DynamoDbRedirectRepository

TABLE_NAME = "test-redirects"
REGION = "eu-central-1"


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=REGION)
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "short_code", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "short_code", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def repo(dynamodb_table) -> DynamoDbRedirectRepository:
    """Create a DynamoDB repository against the mocked table."""
    return DynamoDbRedirectRepository(
        table_name=TABLE_NAME,
        region=REGION,
    )


@pytest.fixture
def seeded_repo(repo: DynamoDbRedirectRepository) -> DynamoDbRedirectRepository:
    """Seed the repository with test data."""
    repo.add_redirect(
        short_code="heise",
        destination_url="https://www.heise.de",
        status_code=302,
        owner_group="engineering",
        public=False,
    )
    repo.add_redirect(
        short_code="google",
        destination_url="https://www.google.com",
        status_code=301,
        owner_group="engineering",
        public=True,
    )
    repo.add_redirect(
        short_code="jira",
        destination_url="https://jira.example.com",
        status_code=302,
        owner_group="it",
        public=True,
    )
    repo.add_redirect(
        short_code="private-mkt",
        destination_url="https://marketing.example.com",
        status_code=302,
        owner_group="marketing",
        public=False,
    )
    repo.add_redirect(
        short_code="legacy",
        destination_url="https://legacy.example.com",
        status_code=302,
        owner_group=None,
        public=True,
    )
    # Add a disabled entry manually
    repo.add_redirect(
        short_code="disabled",
        destination_url="https://disabled.example.com",
        status_code=302,
        owner_group="engineering",
        public=False,
    )
    repo.set_enabled("disabled", enabled=False)
    return repo


class TestDynamoDbGetRedirect:
    """Test get_redirect method."""

    def test_returns_entry_when_found(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert result.short_code == "heise"
        assert result.destination_url == "https://www.heise.de"
        assert result.status_code == 302
        assert result.owner_group == "engineering"
        assert result.public is False
        assert result.enabled is True

    def test_returns_none_when_not_found(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("nonexistent")
        assert result is None

    def test_lookup_normalizes_case(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("HEISE")
        assert result is not None
        assert result.short_code == "heise"

    def test_returns_disabled_entry(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("disabled")
        assert result is not None
        assert result.enabled is False

    def test_returns_entry_with_created_at(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert isinstance(result.created_at, datetime)


class TestDynamoDbListRedirects:
    """Test list_redirects method."""

    def test_returns_only_enabled(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_redirects()
        codes = [r.short_code for r in results]
        assert "heise" in codes
        assert "disabled" not in codes

    def test_returns_ordered(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        results = seeded_repo.list_redirects()
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestDynamoDbListPublic:
    """Test list_public method."""

    def test_returns_public_entries(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert "google" in codes
        assert "jira" in codes
        assert "legacy" in codes

    def test_excludes_private_entries(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert "heise" not in codes
        assert "private-mkt" not in codes

    def test_excludes_disabled(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert "disabled" not in codes

    def test_returns_ordered(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        results = seeded_repo.list_public()
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestDynamoDbListByGroups:
    """Test list_by_groups method."""

    def test_returns_group_entries_plus_public(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "heise" in codes
        assert "google" in codes
        assert "jira" in codes  # public
        assert "legacy" in codes  # public

    def test_excludes_private_from_other_groups(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "private-mkt" not in codes

    def test_empty_groups_returns_public_only(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        results = seeded_repo.list_by_groups([])
        codes = [r.short_code for r in results]
        assert "google" in codes
        assert "jira" in codes
        assert "heise" not in codes

    def test_excludes_disabled(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert "disabled" not in codes

    def test_returns_ordered(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        results = seeded_repo.list_by_groups(["engineering"])
        codes = [r.short_code for r in results]
        assert codes == sorted(codes)


class TestDynamoDbAddRedirect:
    """Test add_redirect method."""

    def test_adds_entry(self, repo: DynamoDbRedirectRepository) -> None:
        entry = repo.add_redirect(
            short_code="test",
            destination_url="https://test.com",
            status_code=302,
            owner_group="engineering",
            public=False,
        )
        assert entry.short_code == "test"
        assert entry.destination_url == "https://test.com"
        assert entry.enabled is True

    def test_entry_is_retrievable(self, repo: DynamoDbRedirectRepository) -> None:
        repo.add_redirect(
            short_code="test",
            destination_url="https://test.com",
            status_code=301,
            owner_group="it",
            public=True,
        )
        result = repo.get_redirect("test")
        assert result is not None
        assert result.status_code == 301
        assert result.owner_group == "it"
        assert result.public is True


class TestDynamoDbDeleteRedirect:
    """Test delete_redirect method."""

    def test_deletes_existing(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        assert seeded_repo.delete_redirect("heise") is True
        assert seeded_repo.get_redirect("heise") is None

    def test_returns_false_for_nonexistent(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        assert seeded_repo.delete_redirect("nonexistent") is False


class TestDynamoDbSetEnabled:
    """Test set_enabled method."""

    def test_disables_entry(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        assert seeded_repo.set_enabled("heise", enabled=False) is True
        result = seeded_repo.get_redirect("heise")
        assert result is not None
        assert result.enabled is False

    def test_enables_entry(self, seeded_repo: DynamoDbRedirectRepository) -> None:
        assert seeded_repo.set_enabled("disabled", enabled=True) is True
        result = seeded_repo.get_redirect("disabled")
        assert result is not None
        assert result.enabled is True

    def test_returns_false_for_nonexistent(
        self, seeded_repo: DynamoDbRedirectRepository
    ) -> None:
        assert seeded_repo.set_enabled("nonexistent", enabled=False) is False
